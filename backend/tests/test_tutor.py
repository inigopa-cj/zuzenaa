"""Tutor RAG: troceado, recuperación acotada, feedback propio, privacidad y permisos."""

import io
import json
from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, UploadFile

from zuzenaa.api.tutor import ChatIn, chat, upload_document
from zuzenaa.auth import roles
from zuzenaa.db.models import Analysis, Repository, User
from zuzenaa.db.session import SessionLocal, init_models
from zuzenaa.github.cli import GhCli
from zuzenaa.github.models import Student
from zuzenaa.privacy import pseudonyms
from zuzenaa.tutor import chunking, service, store
from zuzenaa.tutor.embeddings import HashingEmbedder, cosine
from zuzenaa.util import now_epoch

MATERIAL = """# Tema 3: listas

## Media de una lista

Para calcular la media se suman los elementos y se divide entre la cantidad. Antes de
dividir comprueba si la lista está vacía: dividir entre cero provoca un error.

```python
def media(xs):
    return sum(xs) / len(xs)
```

## La mediana

La mediana es el valor central de la lista ordenada. Si hay un número par de elementos,
es la media de los dos valores centrales.
"""


def _user(login: str) -> User:
    return User(github_id=1, login=login, encrypted_token="x", created_at=0, updated_at=0)


def _gh(staff: list[str]) -> GhCli:
    fake = AsyncMock(spec=GhCli)
    fake.staff.return_value = [Student(username=login) for login in staff]
    return cast(GhCli, fake)


def test_chunking_keeps_headings_and_drops_code() -> None:
    chunks = chunking.split(MATERIAL)
    assert [c.heading for c in chunks] == ["Media de una lista", "La mediana"]
    assert all("def media" not in c.text and "```" not in c.text for c in chunks)
    long = chunking.split("Frase larga. " * 200, max_chars=300)
    assert len(long) > 1 and all(len(c.text) <= 300 for c in long)


def test_hashing_embedder_is_deterministic_and_topical() -> None:
    embedder = HashingEmbedder()
    question = embedder.embed("¿Cómo calculo la mediana de una lista?")
    assert question == embedder.embed("¿Cómo calculo la mediana de una lista?")
    related = embedder.embed("La mediana es el valor central de la lista ordenada")
    unrelated = embedder.embed("Configura el puerto de la web en el fichero de entorno")
    assert cosine(question, related) > cosine(question, unrelated)


async def _student_with_feedback(org: str, room: str, login: str, first: str, last: str) -> None:
    await pseudonyms.ensure_roster(
        org, room, [Student(username=login, first_name=first, last_name=last)]
    )
    now = now_epoch()
    async with SessionLocal() as session:
        repo = Repository(
            org=org, classroom=room, assignment="p2", owner=login,
            repo_full_name=f"{room}-p2-{login}", path="/tmp/none", head_sha="d" * 40,
            head_committed_at=now, last_synced_at=now, status="ok",
            created_at=now, updated_at=now,
        )
        session.add(repo)
        await session.flush()
        feedback = {
            "funcionalidad": f"Falla test_mediana. Autor del fichero: {login}.",
            "calidad": "Añade un caso de prueba para la lista vacía.",
            "diseno": "Separa el cálculo de la mediana en su propia función.",
            "pista": {"level": 2, "text": "Ordena la lista antes de buscar el valor central."},
        }
        session.add(
            Analysis(
                repository_id=repo.id, commit_sha="d" * 40, commit_committed_at=now,
                snapshot_path="/tmp/s", provider="mock", feedback_json=json.dumps(feedback),
                feedback_md="x", evolution=None, created_at=now, forced=False,
            )
        )
        await session.commit()


async def test_search_is_scoped_to_the_classroom_plus_zuzenaa_guide() -> None:
    await init_models()
    await store.ensure_builtin()
    await store.ingest(title="Apuntes", text=MATERIAL, source="material", org="t", classroom="c1")

    own = await store.search("t", "c1", "¿qué es la mediana de una lista?")
    assert own and own[0].source == "material" and own[0].heading == "La mediana"
    other = await store.search("t", "c2", "¿qué es la mediana de una lista?")
    assert all(p.source != "material" for p in other)  # nunca material de otra clase
    guide = await store.search("t", "c2", "¿qué significa el aviso sin avance?")
    assert guide and guide[0].source == "zuzenaa"


async def test_ask_uses_only_own_feedback_and_never_personal_data() -> None:
    await init_models()
    await store.ensure_builtin()
    org, room = "t", "c3"
    await store.ingest(title="Apuntes", text=MATERIAL, source="material", org=org, classroom=room)
    await _student_with_feedback(org, room, "ane-urrutia", "Ane", "Urrutia Garmendia")
    await _student_with_feedback(org, room, "jon-agirre", "Jon", "Agirre Lasa")

    reply = await service.ask(
        org=org,
        classroom=room,
        question="Soy Ane Urrutia (ane-urrutia): ¿por qué falla test_mediana en mi entrega?",
        login="ane-urrutia",
        assignment="p2",
    )
    assert not reply.blocked
    assert reply.citations, reply.answer
    text = json.dumps([reply.answer, [vars(c) for c in reply.citations]], ensure_ascii=False)
    for personal in ("ane-urrutia", "Urrutia", "Garmendia", "jon-agirre", "Agirre"):
        assert personal.lower() not in text.lower(), personal
    feedback = [c for c in reply.citations if c.source == "feedback"]
    assert feedback and all(c.ref.startswith("analysis-") for c in feedback)
    assert "```" not in reply.answer and "def media" not in reply.answer


async def test_chat_permissions_and_upload_rules() -> None:
    await init_models()
    org, room = "t", "c4"
    await _student_with_feedback(org, room, "miren", "Miren", "Arana Etxe")
    roles.clear_cache()

    question = ChatIn.model_validate({"question": "¿qué es la mediana?"})
    reply = await chat(org, room, question, user=_user("miren"), gh=_gh(["tutor"]))
    assert reply.provider == "mock"

    roles.clear_cache()
    with pytest.raises(HTTPException) as exc:  # no es de esta clase
        await chat(org, room, question, user=_user("ajeno"), gh=_gh(["tutor"]))
    assert exc.value.status_code == 403

    roles.clear_cache()
    alias = await pseudonyms.alias_for(org, room, "miren")
    preview = ChatIn.model_validate({"question": "¿qué es la mediana?", "as": alias})
    assert (await chat(org, room, preview, user=_user("tutor"), gh=_gh(["tutor"]))).answer

    def upload(name: str) -> UploadFile:
        return UploadFile(io.BytesIO(MATERIAL.encode()), filename=name)

    with pytest.raises(HTTPException) as exc:  # el alumnado no sube material
        await upload_document(
            org, room, user=_user("miren"), gh=_gh(["tutor"]), file=upload("a.md")
        )
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        await upload_document(
            org, room, user=_user("tutor"), gh=_gh(["tutor"]), file=upload("a.pdf")
        )
    assert exc.value.status_code == 415
    doc = await upload_document(
        org, room, user=_user("tutor"), gh=_gh(["tutor"]), file=upload("tema3.md")
    )
    assert (doc.title, doc.chunk_count) == ("tema3", 2)


async def test_greetings_or_unrelated_questions_get_no_passages() -> None:
    await init_models()
    await store.ensure_builtin()
    await store.ingest(title="Apuntes", text=MATERIAL, source="material", org="t", classroom="c5")
    reply = await service.ask(org="t", classroom="c5", question="hola", login=None)
    assert reply.citations == []


async def test_answer_picks_relevant_sentences_and_refuses_to_write_code() -> None:
    await init_models()
    await store.ensure_builtin()
    reply = await service.ask(
        org="t", classroom="c6", question="¿Qué significa el aviso sin avance?", login=None
    )
    assert "Sin avance" in reply.answer  # la frase relevante, no las primeras de la sección
    code = await service.ask(
        org="t", classroom="c6", question="hazme el código de la media", login=None
    )
    assert code.answer.startswith("No escribo código")


async def test_material_is_found_from_test_names_and_code_requests() -> None:
    await init_models()
    await store.ensure_builtin()
    await store.ingest(title="Apuntes", text=MATERIAL, source="material", org="t", classroom="c7")
    why = await service.ask(
        org="t", classroom="c7", question="¿por qué falla test_mediana?", login=None
    )
    assert any(c.heading == "La mediana" for c in why.citations)
    code = await service.ask(
        org="t", classroom="c7", question="hazme el código de la mediana", login=None
    )
    assert code.citations and code.citations[0].heading == "La mediana"


async def _analysis_id(org: str, room: str, login: str) -> int:
    from sqlalchemy import select

    async with SessionLocal() as session:
        return (
            await session.execute(
                select(Analysis.id)
                .join(Repository, Analysis.repository_id == Repository.id)
                .where(
                    Repository.org == org,
                    Repository.classroom == room,
                    Repository.owner == login,
                )
            )
        ).scalar_one()


async def test_chat_from_a_correction_and_send_it_to_the_teacher() -> None:
    from zuzenaa.api.repos import list_repos
    from zuzenaa.api.tutor import ShareIn, list_shares, mark_read, send_to_teacher

    await init_models()
    org, room = "t", "c8"
    await _student_with_feedback(org, room, "ane-urrutia", "Ane", "Urrutia Garmendia")
    await _student_with_feedback(org, room, "jon-agirre", "Jon", "Agirre Lasa")
    await store.ingest(title="Apuntes", text=MATERIAL, source="material", org=org, classroom=room)
    ane_analysis = await _analysis_id(org, room, "ane-urrutia")
    jon_analysis = await _analysis_id(org, room, "jon-agirre")
    ane = await pseudonyms.alias_for(org, room, "ane-urrutia")
    roles.clear_cache()

    # Desde su corrección: es la primera fuente citada.
    ask = ChatIn.model_validate({"question": "¿qué tengo que mirar?", "analysis_id": ane_analysis})
    reply = await chat(org, room, ask, user=_user("ane-urrutia"), gh=_gh(["tutor"]))
    assert reply.citations and reply.citations[0].source == "correccion"
    mediana = ChatIn.model_validate(
        {"question": "¿qué es la mediana?", "analysis_id": ane_analysis}
    )
    with_material = await chat(org, room, mediana, user=_user("ane-urrutia"), gh=_gh(["tutor"]))
    assert [c.source for c in with_material.citations][:2] == ["correccion", "material"]
    # La corrección de otro alumno no existe para ella.
    other = ChatIn.model_validate({"question": "¿y esta?", "analysis_id": jon_analysis})
    with pytest.raises(HTTPException) as exc:
        await chat(org, room, other, user=_user("ane-urrutia"), gh=_gh(["tutor"]))
    assert exc.value.status_code == 404

    # Envía la duda al profesorado: se guarda con su seudónimo, nunca con su nombre.
    share_in = ShareIn.model_validate(
        {
            "analysis_id": ane_analysis,
            "note": "Soy Ane Urrutia y no entiendo la pista",
            "transcript": [
                {"role": "user", "text": "¿qué tengo que mirar? (ane-urrutia)"},
                {"role": "tutor", "text": reply.answer},
            ],
        }
    )
    sent = await send_to_teacher(org, room, "p2", ane, share_in, user=_user("ane-urrutia"))
    stored = json.dumps(sent.model_dump(), ensure_ascii=False)
    assert "Urrutia" not in stored and "ane-urrutia" not in stored and ane in stored

    with pytest.raises(HTTPException) as exc:  # nadie envía en nombre de otro
        await send_to_teacher(org, room, "p2", ane, share_in, user=_user("jon-agirre"))
    assert exc.value.status_code == 403

    # El profesor la ve como pendiente en la tabla de entregas y la marca como leída.
    rows = await list_repos(org, room, "p2", user=_user("tutor"), gh=_gh(["tutor"]))
    assert next(r for r in rows if r.owner == ane).pending_questions == 1
    shares = await list_shares(org, room, "p2", ane, user=_user("tutor"), gh=_gh(["tutor"]))
    assert [s.id for s in shares] == [sent.id]
    with pytest.raises(HTTPException) as exc:  # la alumna no marca como leído
        await mark_read(org, room, sent.id, user=_user("ane-urrutia"), gh=_gh(["tutor"]))
    assert exc.value.status_code == 403
    read = await mark_read(org, room, sent.id, user=_user("tutor"), gh=_gh(["tutor"]))
    assert read.read_at is not None
    rows = await list_repos(org, room, "p2", user=_user("tutor"), gh=_gh(["tutor"]))
    assert next(r for r in rows if r.owner == ane).pending_questions == 0
    # La propia alumna ve su envío (y que ya se ha leído).
    mine = await list_shares(org, room, "p2", ane, user=_user("ane-urrutia"), gh=_gh(["tutor"]))
    assert mine[0].read_at is not None
