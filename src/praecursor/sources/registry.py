from dataclasses import dataclass


@dataclass(frozen=True)
class SourceCapabilities:
    """Capabilities and integration status for one market data source."""

    name: str
    display_name: str
    status: str
    supports_history: bool
    supports_latest_quote: bool
    supports_consensus: bool
    implemented: bool
    role: str
    notes: str


SOURCE_REGISTRY: tuple[SourceCapabilities, ...] = (
    SourceCapabilities(
        name="yahoo_finance",
        display_name="Yahoo Finance",
        status="implemented",
        supports_history=True,
        supports_latest_quote=True,
        supports_consensus=True,
        implemented=True,
        role="Primary long-history source for indicators.",
        notes="Useful for EMA/RSI history. Third-party source; use under appropriate terms.",
    ),
    SourceCapabilities(
        name="stockanalysis",
        display_name="StockAnalysis",
        status="implemented",
        supports_history=True,
        supports_latest_quote=True,
        supports_consensus=True,
        implemented=True,
        role="Recent-history and latest-close consensus source.",
        notes="Currently useful for recent table data and cross-checking latest close.",
    ),
    SourceCapabilities(
        name="official_egx",
        display_name="Official EGX",
        status="planned",
        supports_history=False,
        supports_latest_quote=True,
        supports_consensus=True,
        implemented=False,
        role="Authoritative validation source.",
        notes="Official website is ASP.NET-style and needs careful implementation.",
    ),
    SourceCapabilities(
        name="mubasher",
        display_name="Mubasher Info",
        status="planned",
        supports_history=False,
        supports_latest_quote=True,
        supports_consensus=True,
        implemented=False,
        role="Regional market-data cross-check source.",
        notes="Pages show delayed quotes; suitable candidate for latest quote validation.",
    ),
    SourceCapabilities(
        name="tradingview",
        display_name="TradingView",
        status="research_required",
        supports_history=False,
        supports_latest_quote=True,
        supports_consensus=True,
        implemented=False,
        role="Potential extra quote/signal confirmation source.",
        notes="Scraping may be fragile/restricted; must verify allowed usage before integration.",
    ),
    SourceCapabilities(
        name="investingpro",
        display_name="InvestingPro",
        status="deferred",
        supports_history=False,
        supports_latest_quote=False,
        supports_consensus=False,
        implemented=False,
        role="Potential premium source if user provides legal access later.",
        notes="May require subscription/login; not suitable for unauthenticated open-source scraping now.",
    ),
)


def list_sources() -> list[SourceCapabilities]:
    return list(SOURCE_REGISTRY)


def get_source(name: str) -> SourceCapabilities:
    normalized_name = name.strip().lower()

    for source in SOURCE_REGISTRY:
        if source.name == normalized_name:
            return source

    raise KeyError(f"Unknown data source: {name}")


def implemented_sources() -> list[SourceCapabilities]:
    return [source for source in SOURCE_REGISTRY if source.implemented]


def consensus_candidate_sources() -> list[SourceCapabilities]:
    return [source for source in SOURCE_REGISTRY if source.supports_consensus]
