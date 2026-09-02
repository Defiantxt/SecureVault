"""Pure navigation metadata and filtering for decrypted vault entries.

This module deliberately has no GUI, database, or encryption dependencies.
Callers keep the authoritative records keyed by stable database ID and receive
a new, insertion-ordered dictionary containing only the records for a view.
"""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final, Mapping, TypeVar


class EntryView(str, Enum):
    """Stable identifiers for the entry-list navigation destinations."""

    ALL_ENTRIES = "all_entries"
    FAVORITES = "favorites"
    LOGINS = "logins"
    CARDS = "cards"
    NOTES = "notes"
    TRASH = "trash"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ViewPresentation:
    """User-facing copy associated with an entry view."""

    title: str
    empty_state_label: str


VIEW_PRESENTATIONS: Final[Mapping[EntryView, ViewPresentation]] = (
    MappingProxyType(
        {
            EntryView.ALL_ENTRIES: ViewPresentation(
                title="All Entries",
                empty_state_label="No entries added",
            ),
            EntryView.FAVORITES: ViewPresentation(
                title="Favorites",
                empty_state_label="No favorite entries",
            ),
            EntryView.LOGINS: ViewPresentation(
                title="Logins",
                empty_state_label="No login entries",
            ),
            EntryView.CARDS: ViewPresentation(
                title="Cards",
                empty_state_label="No card entries",
            ),
            EntryView.NOTES: ViewPresentation(
                title="Notes",
                empty_state_label="No note entries",
            ),
            EntryView.TRASH: ViewPresentation(
                title="Trash",
                empty_state_label="Trash is empty",
            ),
        }
    )
)

NAVIGATION_VIEWS: Final[tuple[EntryView, ...]] = tuple(EntryView)
NO_SEARCH_RESULTS_LABEL: Final[str] = "No entries match your search"

EntryId = TypeVar("EntryId")
EntryRecord = Mapping[str, object]


def normalize_view(view: EntryView | str) -> EntryView:
    """Return an ``EntryView`` or raise ``ValueError`` for an unknown ID."""

    if isinstance(view, EntryView):
        return view
    return EntryView(view)


def get_view_presentation(view: EntryView | str) -> ViewPresentation:
    """Return the title and default empty-state label for ``view``."""

    return VIEW_PRESENTATIONS[normalize_view(view)]


def get_empty_state_label(view: EntryView | str, search: str = "") -> str:
    """Return search-aware empty-state copy for an entry list."""

    presentation = get_view_presentation(view)
    if search.strip():
        return NO_SEARCH_RESULTS_LABEL
    return presentation.empty_state_label


def filter_entry_records(
    records: Mapping[EntryId, EntryRecord],
    view: EntryView | str = EntryView.ALL_ENTRIES,
    search: str = "",
) -> dict[EntryId, EntryRecord]:
    """Filter decrypted records by navigation view and then by search text.

    ``deleted_at is None`` (including a missing key during schema migration)
    means active. Every non-trash view excludes deleted records. Search is a
    trimmed, Unicode-aware, case-insensitive substring match over only the
    entry name and type; secret/password/note content is intentionally ignored.

    Iterating the input mapping directly retains its stable IDs and insertion
    order, including when multiple records have the same display name. Neither
    the input mapping nor its record values are mutated.
    """

    selected_view = normalize_view(view)
    query = search.strip().casefold()
    visible: dict[EntryId, EntryRecord] = {}

    for entry_id, record in records.items():
        is_trashed = record.get("deleted_at") is not None
        if selected_view is EntryView.TRASH:
            if not is_trashed:
                continue
        elif is_trashed:
            continue
        elif selected_view is EntryView.FAVORITES:
            if not bool(record.get("favorite", False)):
                continue
        elif selected_view in (
            EntryView.LOGINS,
            EntryView.CARDS,
            EntryView.NOTES,
        ):
            expected_type = {
                EntryView.LOGINS: "login",
                EntryView.CARDS: "card",
                EntryView.NOTES: "note",
            }[selected_view]
            record_type = _normalized_text(record.get("type"))
            if record_type.strip() != expected_type:
                continue

        if query:
            name = _normalized_text(record.get("name"))
            entry_type = _normalized_text(record.get("type"))
            if query not in name and query not in entry_type:
                continue

        visible[entry_id] = record

    return visible


def _normalized_text(value: object) -> str:
    """Normalize a decrypted display value for matching without mutation."""

    if value is None:
        return ""
    return str(value).casefold()
