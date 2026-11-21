"""Business decisions about which tours may be quoted, kept explicit and reviewable.

Generic checks (draft content, "not launched" notes, content/rate duration mismatch)
live in the engine. Tours listed here are blocked for reasons the data cannot express.
"""

NOT_QUOTABLE: dict[str, str] = {
    "T14": "Seasonal offer 'Winter 2023/24 - Early Bird' has ended; page needs updating by staff.",
}
