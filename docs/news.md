# Market news

Open **Workspace → News** in the authorized local dashboard, or go to
`/dashboard/news`. Search headlines or disclosed tickers and filter by category
or source. Each result links to its publisher. Times use Africa/Cairo. Arab
Finance supplies an update timestamp for some items but omits the publication
timestamp. The dashboard labels those times as source updates.

The GitHub Actions News workflow runs daily at 06:20, 12:20 and 18:20 UTC,
subject to runner availability. It collects the official EGX homepage and the
Arab Finance Macroeconomy and Finance and Banking RSS feeds. It publishes a
separate rolling `news.json` release asset of up to 300 links from the last
30 days. The cloud payload contains official notice titles, explicitly
identified symbols, dates, source health, and publisher links with derived
topics. The dashboard reads matching RSS headlines locally under Arab Finance's
personal-use terms. When the headlines leave the RSS window, a topic and
article link remain. The CBE page rejected the automated request during source
verification, so central-bank coverage comes through the enabled feeds.
[EGX](https://beta.egx.com.eg/en) · [Arab Finance RSS](https://www.arabfinance.com/en/RSS/RSSList) · [Publisher terms](https://www.arabfinance.com/en/home/terms)

The local dashboard checks for a newly published index at most once per five
minutes during normal operation. It retains the last cloud snapshot on disk,
reports source-specific failures, and marks a cloud snapshot stale after
14 hours. It retries a failed cloud fetch on the next view request after one
minute. Open the GitHub Actions News workflow and select **Run workflow** to
request an extra cloud refresh.

The collector consolidates repeated canonical source links and preserves
first-seen, last-seen, and observed revision timestamps for the retained
window. Matching financial-results cross-posts link to the official disclosure with attachments. EGX homepage rows cover a partial source window. The News workflow
touches only its own release and runs separately from scanner state, research,
training, and notifications.
