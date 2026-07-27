from praecursor.sources.registry import list_sources


def main() -> int:
    sources = list_sources()

    print("Praecursor-EGX data source registry")
    print()
    print(f"{'Name':<18} {'Status':<18} {'History':<8} {'Latest':<8} {'Consensus':<10} Role")
    print("-" * 100)

    for source in sources:
        print(
            f"{source.name:<18} "
            f"{source.status:<18} "
            f"{_yes_no(source.supports_history):<8} "
            f"{_yes_no(source.supports_latest_quote):<8} "
            f"{_yes_no(source.supports_consensus):<10} "
            f"{source.role}"
        )

    print()
    print("Notes")
    for source in sources:
        print(f"- {source.display_name}: {source.notes}")

    return 0


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


if __name__ == "__main__":
    raise SystemExit(main())
