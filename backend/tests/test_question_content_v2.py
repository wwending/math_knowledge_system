from uuid import uuid4

import pytest

from app.services.question_content import (
    ContentSnapshotError,
    build_draft_v2_snapshot,
    build_legacy_v2_snapshot,
    normalize_v2_snapshot,
    project_legacy_text,
    replace_legacy_text,
    snapshot_figure_ids,
)


def test_snapshot_uuid_values_use_shared_canonical_form():
    figure_id = str(uuid4()).upper()
    snapshot = build_legacy_v2_snapshot(
        content=None,
        answer=None,
        analysis=None,
        seed="canonical-uuid",
        figure_id=figure_id,
    )

    assert snapshot["sections"]["stem"]["blocks"][0]["placements"][0]["figure_id"] == figure_id.lower()


def test_legacy_projection_is_deterministic_and_preserves_flat_text():
    first = build_legacy_v2_snapshot(
        content="题干",
        answer="答案",
        analysis="解析",
        seed="question:7",
    )
    second = build_legacy_v2_snapshot(
        content="题干",
        answer="答案",
        analysis="解析",
        seed="question:7",
    )

    assert first == second
    assert first["schema_version"] == 2
    assert project_legacy_text(first) == {
        "content": "题干",
        "answer": "答案",
        "analysis": "解析",
    }


def test_draft_snapshot_packs_natural_sizes_and_wraps_deterministically():
    figures = [
        {"figure_id": str(uuid4()), "width": 60, "height": 20},
        {"figure_id": str(uuid4()), "width": 40, "height": 30},
        {"figure_id": str(uuid4()), "width": 70, "height": 35},
    ]
    snapshot = build_draft_v2_snapshot(
        content="题干",
        seed="question:129",
        figures=figures,
        canvas_width=100,
    )
    repeated = build_draft_v2_snapshot(
        content="题干",
        seed="question:129",
        figures=figures,
        canvas_width=100,
    )

    assert snapshot == repeated
    blocks = snapshot["sections"]["stem"]["blocks"]
    assert [block["kind"] for block in blocks] == ["text", "image_area"]
    area = blocks[1]
    assert area["height_ratio"] == pytest.approx(0.65)
    assert [placement["figure_id"] for placement in area["placements"]] == [
        figure["figure_id"] for figure in figures
    ]
    assert area["placements"] == [
        {
            "figure_id": figures[0]["figure_id"],
            "x": 0.0,
            "y": 0.0,
            "width": 0.6,
            "height": pytest.approx(20 / 65),
        },
        {
            "figure_id": figures[1]["figure_id"],
            "x": 0.6,
            "y": 0.0,
            "width": 0.4,
            "height": pytest.approx(30 / 65),
        },
        {
            "figure_id": figures[2]["figure_id"],
            "x": 0.0,
            "y": pytest.approx(30 / 65),
            "width": 0.7,
            "height": pytest.approx(35 / 65),
        },
    ]


def test_pure_image_stem_and_empty_optional_sections_are_valid():
    figure_id = str(uuid4())
    snapshot = build_legacy_v2_snapshot(
        content=None,
        answer=None,
        analysis=None,
        seed="question:8",
        figure_id=figure_id,
        figure_aspect_ratio=0.5,
    )

    assert project_legacy_text(snapshot) == {
        "content": None,
        "answer": None,
        "analysis": None,
    }
    assert snapshot_figure_ids(snapshot) == {figure_id}
    assert snapshot["sections"]["stem"]["blocks"][0]["height_ratio"] == 0.5


def test_multi_figure_image_area_is_expressible():
    first_figure = str(uuid4())
    second_figure = str(uuid4())
    snapshot = {
        "schema_version": 2,
        "sections": {
            "stem": {
                "blocks": [
                    {
                        "id": str(uuid4()),
                        "kind": "image_area",
                        "height_ratio": 0.75,
                        "placements": [
                            {
                                "figure_id": first_figure,
                                "x": 0,
                                "y": 0,
                                "width": 0.5,
                                "height": 1,
                            },
                            {
                                "figure_id": second_figure,
                                "x": 0.5,
                                "y": 0,
                                "width": 0.5,
                                "height": 1,
                            },
                        ],
                    }
                ]
            },
            "answer": {"blocks": []},
            "analysis": {"blocks": []},
        },
    }

    normalized = normalize_v2_snapshot(snapshot)
    assert snapshot_figure_ids(normalized) == {first_figure, second_figure}


def test_image_areas_do_not_inject_markers_into_flat_projection():
    figure_id = str(uuid4())
    snapshot = build_legacy_v2_snapshot(
        content="第一段",
        answer=None,
        analysis=None,
        seed="question:9",
        figure_id=figure_id,
    )
    snapshot["sections"]["stem"]["blocks"].append(
        {"id": str(uuid4()), "kind": "text", "markdown": "第二段"}
    )

    assert project_legacy_text(snapshot)["content"] == "第一段\n\n第二段"


def test_incomplete_legacy_row_is_explicit_but_new_empty_stem_is_rejected():
    legacy = build_legacy_v2_snapshot(
        content=None,
        answer=None,
        analysis=None,
        seed="question:10",
    )
    assert legacy["compatibility_state"] == "incomplete_stem"

    invalid = {
        "schema_version": 2,
        "sections": {
            "stem": {"blocks": []},
            "answer": {"blocks": []},
            "analysis": {"blocks": []},
        },
    }
    with pytest.raises(ContentSnapshotError, match="stem"):
        normalize_v2_snapshot(invalid)


def test_flat_text_edit_preserves_image_areas_and_stable_ids():
    figure_id = str(uuid4())
    snapshot = build_legacy_v2_snapshot(
        content="old",
        answer=None,
        analysis=None,
        seed="question:11",
        figure_id=figure_id,
    )
    old_blocks = snapshot["sections"]["stem"]["blocks"]

    updated = replace_legacy_text(
        snapshot,
        content="new",
        answer="answer",
        analysis=None,
        seed="question:11",
    )
    new_blocks = updated["sections"]["stem"]["blocks"]

    assert new_blocks[0]["id"] == old_blocks[0]["id"]
    assert new_blocks[1] == old_blocks[1]
    assert project_legacy_text(updated)["content"] == "new"
    assert snapshot_figure_ids(updated) == {figure_id}


def test_unknown_versions_and_out_of_bounds_placements_are_rejected():
    with pytest.raises(ContentSnapshotError, match="schema_version"):
        normalize_v2_snapshot({"schema_version": 3, "sections": {}})

    invalid = {
        "schema_version": 2,
        "sections": {
            "stem": {
                "blocks": [
                    {
                        "id": str(uuid4()),
                        "kind": "image_area",
                        "height_ratio": 1,
                        "placements": [
                            {
                                "figure_id": str(uuid4()),
                                "x": 0.8,
                                "y": 0,
                                "width": 0.3,
                                "height": 1,
                            }
                        ],
                    }
                ]
            },
            "answer": {"blocks": []},
            "analysis": {"blocks": []},
        },
    }
    with pytest.raises(ContentSnapshotError, match="fit"):
        normalize_v2_snapshot(invalid)


def test_figure_can_be_placed_only_once_across_the_whole_document():
    figure_id = str(uuid4())
    snapshot = {
        "schema_version": 2,
        "sections": {
            "stem": {"blocks": [{
                "id": str(uuid4()), "kind": "image_area", "height_ratio": 1,
                "placements": [{"figure_id": figure_id, "x": 0, "y": 0, "width": 1, "height": 1}],
            }]},
            "answer": {"blocks": [{
                "id": str(uuid4()), "kind": "image_area", "height_ratio": 1,
                "placements": [{"figure_id": figure_id, "x": 0, "y": 0, "width": 1, "height": 1}],
            }]},
            "analysis": {"blocks": []},
        },
    }
    with pytest.raises(ContentSnapshotError) as captured:
        normalize_v2_snapshot(snapshot)
    assert captured.value.code == "duplicate_figure_placement"
    assert captured.value.section == "answer"
    assert captured.value.placement_index == 0
    assert captured.value.figure_id == figure_id


def test_non_finite_layout_numbers_are_rejected():
    for field, value in (("x", float("nan")), ("height_ratio", float("inf"))):
        block = {
            "id": str(uuid4()),
            "kind": "image_area",
            "height_ratio": 1,
            "placements": [
                {
                    "figure_id": str(uuid4()),
                    "x": 0,
                    "y": 0,
                    "width": 1,
                    "height": 1,
                }
            ],
        }
        if field == "height_ratio":
            block[field] = value
        else:
            block["placements"][0][field] = value
        snapshot = {
            "schema_version": 2,
            "sections": {
                "stem": {"blocks": [block]},
                "answer": {"blocks": []},
                "analysis": {"blocks": []},
            },
        }
        with pytest.raises(ContentSnapshotError, match="finite"):
            normalize_v2_snapshot(snapshot)
