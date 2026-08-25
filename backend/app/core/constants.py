class DraftStatus:
    DRAFT_CREATED = "draft_created"
    RECOGNIZING = "recognizing"
    DRAFT_READY = "draft_ready"
    FAILED = "failed"
    SUPERSEDED = "superseded"
    SAVED_TO_BANK = "saved_to_bank"

    # Legacy aliases
    DRAFT = DRAFT_CREATED
    REVIEWED = DRAFT_READY
    OCR_DONE = DRAFT_READY
    LLM_DONE = DRAFT_READY
    PUBLISHED = SAVED_TO_BANK
    ARCHIVED = SUPERSEDED


class DraftEventType:
    CREATE = "create"
    START_RECOGNIZE = "start_recognize"
    RECOGNIZE_SUCCESS = "recognize_success"
    RECOGNIZE_FAIL = "recognize_fail"
    SAVE_TO_BANK = "save_to_bank"
    EDIT = "edit"
    RECROP = "recrop"

    # Legacy aliases (deprecated)
    STATUS_TRANSITION = "status_transition"
    OCR_COMPLETED = RECOGNIZE_SUCCESS
    LLM_COMPLETED = RECOGNIZE_SUCCESS
    MANUAL = EDIT
    SYSTEM = STATUS_TRANSITION


_STATUS_NORMALIZATION_MAP = {
    "draft": DraftStatus.DRAFT_CREATED,
    "draft_created": DraftStatus.DRAFT_CREATED,
    "recognizing": DraftStatus.RECOGNIZING,
    "draft_ready": DraftStatus.DRAFT_READY,
    "reviewed": DraftStatus.DRAFT_READY,
    "ocr_done": DraftStatus.DRAFT_READY,
    "llm_done": DraftStatus.DRAFT_READY,
    "failed": DraftStatus.FAILED,
    "superseded": DraftStatus.SUPERSEDED,
    "published": DraftStatus.SAVED_TO_BANK,
    "saved_to_bank": DraftStatus.SAVED_TO_BANK,
    "archived": DraftStatus.SUPERSEDED,
}


_EVENT_TYPE_NORMALIZATION_MAP = {
    "create": DraftEventType.CREATE,
    "start_recognize": DraftEventType.START_RECOGNIZE,
    "recognize_success": DraftEventType.RECOGNIZE_SUCCESS,
    "recognize_fail": DraftEventType.RECOGNIZE_FAIL,
    "save_to_bank": DraftEventType.SAVE_TO_BANK,
    "edit": DraftEventType.EDIT,
    "recrop": DraftEventType.RECROP,
    "status_transition": DraftEventType.STATUS_TRANSITION,
    "ocr_completed": DraftEventType.RECOGNIZE_SUCCESS,
    "llm_completed": DraftEventType.RECOGNIZE_SUCCESS,
    "manual": DraftEventType.EDIT,
    "system": DraftEventType.STATUS_TRANSITION,
}


def normalize_status(value: str) -> str:
    if value is None:
        return value
    key = value.lower()
    return _STATUS_NORMALIZATION_MAP.get(key, value)


def normalize_event_type(value: str) -> str:
    if value is None:
        return value
    key = value.lower()
    return _EVENT_TYPE_NORMALIZATION_MAP.get(key, value)


# Upload limits and allowed asset types.
MAX_ASSET_SIZE_BYTES = 20 * 1024 * 1024
ALLOWED_ASSET_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "application/pdf",
}

# Legacy upload_pdf limits (#103): each page is rendered to a JPG at 2x matrix,
# so both the file size and the page count must stay bounded per request.
MAX_PDF_PAGES = 50
# pdf_temp TTL (#103): legacy upload_pdf leaves the PDF and its page renders in
# pdf_temp with no other lifecycle; stale files are swept best-effort.
PDF_TEMP_TTL_SECONDS = 24 * 60 * 60

# Feedback inbox (#98): screenshots are evidence images only — the shared asset
# whitelist above also allows PDFs, which must not leak into feedback uploads.
ALLOWED_FEEDBACK_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
}
MAX_FEEDBACK_SCREENSHOTS = 5
