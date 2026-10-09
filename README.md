# Crypto Breakout Map

A single web page that analyses every tradable spot/USDT coin in the viewer's browser:
market phase (bull / bear / sideways), 30-day breakout trigger prices, an estimated date window
for the next breakout, the measured move afterwards, volume, market cap, and a
Trigger + OCO trade plan for each coin.

Data comes live from public exchange and CoinGecko APIs each time the page is opened, and news.json
is rebuilt every 30 minutes from public crypto news feeds by a scheduled GitHub Action;
the open coin streams live, all prices refresh every 10 seconds and the analysis re-runs every
30 minutes with the current day's candle. Nothing is stored on a server.

This is analysis, not financial advice. The breakout plan shown on the page was backtested and did
not show an edge; the page says so next to every plan.
