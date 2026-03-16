"""Generate the IntraTrading Daily Guide PDF."""

from fpdf import FPDF


class TradingGuide(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 8, "IntraTrading - Daily Guide", align="R")
            self.ln(12)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title, r=30, g=30, b=30):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(r, g, b)
        self.cell(0, 10, title)
        self.ln(6)
        self.set_draw_color(220, 120, 50)
        self.set_line_width(0.8)
        self.line(10, self.get_y(), 80, self.get_y())
        self.ln(6)

    def sub_title(self, title, r=50, g=50, b=50):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(r, g, b)
        self.cell(0, 8, title)
        self.ln(7)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def bullet(self, text, indent=15):
        x = self.get_x()
        self.set_font("Helvetica", "", 10)
        self.set_text_color(60, 60, 60)
        self.set_x(indent)
        self.cell(5, 5.5, "-")
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def numbered(self, num, text, bold_part="", indent=15):
        self.set_x(indent)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(220, 120, 50)
        self.cell(8, 5.5, f"{num}.")
        if bold_part:
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(40, 40, 40)
            self.cell(self.get_string_width(bold_part) + 2, 5.5, bold_part)
            self.set_font("Helvetica", "", 10)
            self.set_text_color(60, 60, 60)
            self.multi_cell(0, 5.5, text)
        else:
            self.set_font("Helvetica", "", 10)
            self.set_text_color(60, 60, 60)
            self.multi_cell(0, 5.5, text)
        self.ln(1.5)

    def time_block(self, time, title, desc):
        self.set_x(15)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(220, 120, 50)
        w = self.get_string_width(time) + 4
        self.cell(w, 6, time)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(40, 40, 40)
        self.cell(0, 6, f"  {title}")
        self.ln(6)
        self.set_x(15)
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(80, 80, 80)
        self.multi_cell(175, 5, desc)
        self.ln(3)

    def table_row(self, cells, widths, bold=False, header=False):
        h = 7
        self.set_font("Helvetica", "B" if bold or header else "", 9)
        if header:
            self.set_fill_color(245, 245, 245)
            self.set_text_color(80, 80, 80)
        else:
            self.set_text_color(60, 60, 60)
        for i, (cell, w) in enumerate(zip(cells, widths)):
            align = "C" if i > 0 and not header else "L"
            if header:
                align = "C" if i > 0 else "L"
            self.cell(w, h, cell, border=1, align=align, fill=header)
        self.ln(h)


def generate():
    pdf = TradingGuide()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Cover / Title Page ──
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 15, "IntraTrading", align="C")
    pdf.ln(14)
    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(220, 120, 50)
    pdf.cell(0, 10, "Daily Trading Guide", align="C")
    pdf.ln(20)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 7, "Automated Intraday & Swing Trading System", align="C")
    pdf.ln(7)
    pdf.cell(0, 7, "Nifty 500 | 6 Technical Strategies | Fyers Broker", align="C")
    pdf.ln(30)

    # Quick info box
    pdf.set_draw_color(220, 120, 50)
    pdf.set_line_width(0.5)
    pdf.rect(40, pdf.get_y(), 130, 35)
    y = pdf.get_y() + 5
    pdf.set_xy(45, y)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(60, 6, "Backend:")
    pdf.set_text_color(40, 40, 40)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(60, 6, "python main.py  (port 8001)")
    pdf.ln(6)
    pdf.set_x(45)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(60, 6, "Frontend:")
    pdf.set_text_color(40, 40, 40)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(60, 6, "npm run dev  (port 3000)")
    pdf.ln(6)
    pdf.set_x(45)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(60, 6, "App URL:")
    pdf.set_text_color(40, 40, 40)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(60, 6, "http://localhost:3000")
    pdf.ln(6)
    pdf.set_x(45)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(60, 6, "Market Hours:")
    pdf.set_text_color(40, 40, 40)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(60, 6, "9:15 AM - 3:30 PM IST (Mon-Fri)")

    # ── Page 2: Daily Startup Checklist ──
    pdf.add_page()
    pdf.section_title("1. Daily Startup Checklist")
    pdf.body_text("Do this every trading day, ideally 5-10 minutes before 9:15 AM.")
    pdf.ln(2)

    steps = [
        ("Open Terminal  ", "Navigate to the IntraTrading project folder."),
        ("Start Backend  ", 'Run:  cd backend && python main.py\nWait for "Uvicorn running on 0.0.0.0:8001" message.'),
        ("Start Frontend  ", "Open a new terminal tab.\nRun:  cd frontend && npm run dev\nWait for the Vite dev server to start on port 3000."),
        ("Open Browser  ", "Go to http://localhost:3000"),
        ("Login to Fyers  ", 'Click "Connect Fyers" on the Dashboard sidebar. Complete the OAuth login. You\'ll see a green "Connected" status when done.'),
        ("Set Capital  ", "Enter your trading capital (e.g. 1,00,000). The system risks 2% per trade."),
        ("Ready!  ", "Wait for 9:15 AM market open. Then start Auto Trade or Paper Trade."),
    ]
    for i, (bold, text) in enumerate(steps, 1):
        pdf.numbered(i, text, bold)

    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 5, "Tip: You can leave both servers running overnight. They use minimal resources when idle. Just refresh the browser tab the next morning and re-login to Fyers (token expires daily).")

    # ── Page 3: Intraday Trading Day Timeline ──
    pdf.add_page()
    pdf.section_title("2. Intraday Trading Day Timeline")
    pdf.body_text("This is what happens during a typical intraday trading day. All times are IST.")
    pdf.ln(2)

    timeline = [
        ("Before 9:15 AM", "Get Ready",
         "Start servers, login to Fyers, set capital. Everything should be ready before market opens."),
        ("9:15 AM", "Market Opens - Start Trading",
         "Press 'Start' on Auto-Trader or Paper Trader. You CANNOT start before 9:15 AM. First scan runs immediately."),
        ("9:15 AM - 2:00 PM", "Active Trading Window",
         "Engine scans Nifty 500 every 15 minutes. Places bracket orders (entry + SL + target) automatically. Max 3 positions at a time. 2% risk per trade. Monitor on Dashboard."),
        ("2:00 PM", "Order Cutoff",
         "No NEW orders after 2 PM. Existing positions keep running with their SL and target intact."),
        ("2:00 - 3:15 PM", "Position Monitoring",
         "Open trades can still hit target or SL. No new scans or orders placed."),
        ("3:15 PM", "Auto Square-Off",
         "ALL remaining positions are closed at market price. Engine stops automatically."),
        ("3:30 PM", "Market Closes",
         "All intraday positions settled. P&L is final."),
        ("After Market", "Review & Improve",
         "Check Trade Log for all trades. Run EOD Analyst for parameter tuning recommendations."),
    ]
    for time, title, desc in timeline:
        pdf.time_block(time, title, desc)

    # ── Page 4: Swing Trading ──
    pdf.add_page()
    pdf.section_title("3. Swing Trading Mode")
    pdf.body_text("Swing trading holds positions for days to weeks. Positions carry over across trading days until the target or stop-loss is hit.")
    pdf.ln(2)

    pdf.sub_title("How Swing Differs from Intraday")
    pdf.ln(1)

    widths = [65, 60, 60]
    pdf.table_row(["Feature", "Intraday", "Swing"], widths, header=True)
    rows = [
        ["Timeframes", "5m, 15m", "1h, 1d"],
        ["Max Positions", "3", "1 (strict)"],
        ["Order Cutoff", "2:00 PM", "None"],
        ["Auto Square-Off", "3:15 PM", "None"],
        ["Holding Period", "Same day", "Days to weeks"],
        ["Product Type (Fyers)", "INTRADAY (MIS)", "CNC (Delivery)"],
        ["Risk Per Trade", "2%", "2%"],
        ["Scan Interval", "Every 15 min", "1h / 2h / 4h / daily"],
    ]
    for row in rows:
        pdf.table_row(row, widths)

    pdf.ln(5)
    pdf.sub_title("Eligible Strategies for Swing")
    pdf.ln(1)
    pdf.bullet("Play #1 - EMA-EMA Crossover (1h, 1d) -MA crossovers work well on daily charts")
    pdf.bullet("Play #2 - Triple MA Trend Filter (1h, 1d) -Triple MA alignment captures multi-week trends")
    pdf.bullet("Play #5 - BB Squeeze Breakout (1d) -Daily squeezes indicate multi-day breakouts")
    pdf.bullet("Play #6 - BB Contra Mean Reversion (1d) -Daily mean reversion from lower band")
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 5, "Play #3 (VWAP) is excluded because VWAP resets every session - it's purely intraday. Play #4 (Supertrend) is excluded because the Power Zone setup is calibrated for intraday candles.")

    pdf.ln(4)
    pdf.sub_title("Starting Swing Trading")
    pdf.numbered(1, "Go to the Swing Trade page from the sidebar.", "")
    pdf.numbered(2, "Choose Paper or Live mode (use paper first to test).", "")
    pdf.numbered(3, "Select a strategy and timeframe (1h or 1d).", "")
    pdf.numbered(4, "Set scan interval (how often to look for new setups).", "")
    pdf.numbered(5, "Press Start. The engine runs continuously across days.", "")
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 5, "Swing trader does NOT auto-stop. It keeps running until you manually stop it or the position hits its target/SL. Live swing uses CNC product type so Fyers won't auto-square-off your position.")

    # ── Page 5: Strategy Quick Reference ──
    pdf.add_page()
    pdf.section_title("4. Strategy Quick Reference")
    pdf.body_text("All 6 strategies from the Technical Indicator Playbook with their timeframes and key rules.")
    pdf.ln(2)

    # Strategy table
    widths2 = [8, 52, 32, 25, 25, 22, 22]
    pdf.table_row(["#", "Strategy", "Category", "Intraday", "Swing", "Dir", "R:R"], widths2, header=True)
    strats = [
        ["1", "EMA-EMA Crossover", "Trend", "5m, 15m", "1h, 1d", "L & S", "1:2"],
        ["2", "Triple MA Trend", "Trend", "15m", "1h, 1d", "Long", "1:2"],
        ["3", "VWAP Pullback", "Intraday", "5m", "--", "Long", "1:2"],
        ["4", "Supertrend Power", "Intraday", "5m, 15m", "--", "Long", "1:2+"],
        ["5", "BB Squeeze", "Volatility", "15m", "1d", "Long", "1:1.5"],
        ["6", "BB Contra", "Reversion", "5m, 15m", "1d", "Long", "1:1+"],
    ]
    for s in strats:
        pdf.table_row(s, widths2)

    pdf.ln(6)

    # Detailed strategy cards
    details = [
        ("Play #1: EMA-EMA Crossover", "9 EMA, 21 EMA, 50 SMA filter",
         "9 EMA crosses above 21 EMA (BUY) or below (SELL). 50 SMA confirms trend direction.",
         "Opposite crossover or 1:2 target hit.",
         "Below recent swing low (10-candle lookback) for longs."),
        ("Play #2: Triple MA Trend Filter", "20 EMA, 50 SMA, 200 SMA",
         "All 3 MAs stacked (20>50>200) and sloping up. Price pulls back to 20 EMA or 50 SMA. Bullish reversal candle confirms.",
         "20 EMA crosses below 50 SMA, or price closes below 50 SMA, or 1:2 target.",
         "Below the swing low of the pullback (8-candle lookback)."),
        ("Play #3: VWAP Intraday Pullback", "Session VWAP",
         "Price trending above VWAP for 3-5 candles, pulls back to VWAP. Bullish reversal candle at VWAP (within 0.2%).",
         "Last swing high or 1:2 target.",
         "Below swing low of pullback or below VWAP zone."),
        ("Play #4: Supertrend Power Trend", "Supertrend (ATR 10, Mult 3), 20 EMA",
         "Supertrend GREEN (below price). Price above 20 EMA. Price pulls back into Power Zone (between Supertrend and 20 EMA). Bullish candle in zone.",
         "Recent swing high or 1:2 to 1:3 target.",
         "Below the low of the trigger candle."),
        ("Play #5: BB Squeeze Breakout", "Bollinger Bands (20, 2)",
         "Bands squeeze tight (bandwidth < 85% of avg). Strong bullish candle breaks above upper band. Enter next candle above breakout high.",
         "1:1.5 (primary), 1:2 (secondary).",
         "Below the Middle Band (20 SMA)."),
        ("Play #6: BB Contra Mean Reversion", "BB (20, 2), 200 SMA",
         "Price above 200 SMA (uptrend). Price dips to lower BB. Reversal candle at lower band (Hammer/Doji/Engulfing).",
         "Middle Band (20 SMA) -mean reversion.",
         "Below the low of the reversal candle."),
    ]
    for name, indicators, entry, exit_rule, sl in details:
        if pdf.get_y() > 230:
            pdf.add_page()
        pdf.sub_title(name)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(20, 5, "Indicators: ")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(0, 5, indicators)
        pdf.ln(5)

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(30, 130, 76)
        pdf.cell(12, 5, "Entry: ")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(170, 5, entry)

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(50, 50, 200)
        pdf.cell(10, 5, "Exit: ")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(170, 5, exit_rule)

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(200, 50, 50)
        pdf.cell(7, 5, "SL: ")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(170, 5, sl)
        pdf.ln(4)

    # ── Page: App Pages Guide ──
    pdf.add_page()
    pdf.section_title("5. App Pages Guide")
    pdf.ln(1)

    app_pages = [
        ("Dashboard", "Home screen with real-time P&L, open positions, win rate, Fyers balance, and strategy performance. Right sidebar has Fyers login, capital input, and auto-trader controls."),
        ("Paper Trade", "Virtual trading with fake money. Runs identically to auto-trading (scans every 15 min, places virtual orders with SL & target). Perfect for testing strategies."),
        ("Swing Trade", "Multi-day positional trading. Paper or Live mode. Only 4 strategies eligible. Max 1 position. No time cutoff or square-off. Positions carry across days."),
        ("Backtest", "Test any strategy on historical data for a specific date. See what trades would have triggered, outcomes, and overall performance."),
        ("Positions", "View current open positions, order book, and holdings from your Fyers account in real-time."),
        ("Trade Log", "Complete history of ALL trades (auto, paper, swing, swing paper) with strategy tags, P&L, and exit reasons. Filter by source or date range."),
        ("EOD Analyst", "End-of-day analysis. Reviews the day's trades, evaluates strategy performance, recommends parameter adjustments."),
        ("About", "Full documentation of the app, strategies, trading rules, and timeline."),
    ]
    for name, desc in app_pages:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(30, 6, name)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(70, 70, 70)
        pdf.multi_cell(155, 5.5, desc)
        pdf.ln(3)

    # ── Important Notes ──
    pdf.ln(2)
    pdf.section_title("6. Important Notes")
    pdf.ln(1)

    notes = [
        "Trading involves risk. Never trade money you cannot afford to lose.",
        "Always paper trade first to validate strategy performance before going live.",
        "You CANNOT start intraday auto-trading before 9:15 AM or after 3:30 PM.",
        "Fyers login token expires daily. Re-login each morning before trading.",
        "Start servers and login BEFORE 9:15 AM so you're ready at market open.",
        "Market data for scanning comes from yfinance (free). Orders go through Fyers API.",
        "All trades are permanently saved. Use Trade Log to review across days.",
        "Intraday auto-trader stops at 3:15 PM. Restart it manually each day.",
        "Swing trader runs continuously. No need to restart daily.",
        "Swing positions use CNC (delivery) -they are NOT auto-squared-off by Fyers.",
        "Max 1 swing position at a time. Max 3 intraday positions at a time.",
        "Run EOD Analyst after each trading day for parameter improvement suggestions.",
    ]
    for note in notes:
        pdf.bullet(note)

    # ── Quick Commands Reference ──
    pdf.add_page()
    pdf.section_title("7. Quick Commands Reference")
    pdf.ln(1)

    pdf.sub_title("Start Servers")
    pdf.set_font("Courier", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.set_x(15)
    pdf.cell(0, 6, "# Terminal 1 - Backend")
    pdf.ln(6)
    pdf.set_x(15)
    pdf.set_font("Courier", "B", 10)
    pdf.cell(0, 6, "cd backend && python main.py")
    pdf.ln(10)
    pdf.set_font("Courier", "", 10)
    pdf.set_x(15)
    pdf.cell(0, 6, "# Terminal 2 - Frontend")
    pdf.ln(6)
    pdf.set_x(15)
    pdf.set_font("Courier", "B", 10)
    pdf.cell(0, 6, "cd frontend && npm run dev")
    pdf.ln(12)

    pdf.sub_title("Useful URLs")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    urls = [
        ("App", "http://localhost:3000"),
        ("Backend API", "http://localhost:8001"),
        ("API Docs (Swagger)", "http://localhost:8001/docs"),
        ("Fyers API Portal", "https://myapi.fyers.in"),
    ]
    for label, url in urls:
        pdf.set_x(15)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(40, 6, label + ":")
        pdf.set_font("Courier", "", 10)
        pdf.set_text_color(50, 100, 200)
        pdf.cell(0, 6, url)
        pdf.ln(7)

    pdf.ln(6)
    pdf.sub_title("Project Folder Structure")
    pdf.set_font("Courier", "", 9)
    pdf.set_text_color(60, 60, 60)
    tree = [
        "IntraTrading/",
        "  backend/",
        "    main.py              # FastAPI server entry point",
        "    config.py             # Strategy timeframes & trading config",
        "    strategies/           # 6 strategy implementations",
        "    services/",
        "      scanner.py          # Nifty 500 stock scanner",
        "      auto_trader.py      # Live intraday engine",
        "      paper_trader.py     # Virtual intraday engine",
        "      swing_trader.py     # Live swing engine",
        "      swing_paper_trader.py  # Virtual swing engine",
        "      fyers_client.py     # Fyers API integration",
        "      trade_logger.py     # Persistent trade history",
        "    .env                  # Fyers credentials (never commit)",
        "  frontend/",
        "    src/App.jsx           # Main app with routing",
        "    src/components/       # All UI pages",
        "    src/services/api.js   # Backend API calls",
    ]
    for line in tree:
        pdf.set_x(15)
        pdf.cell(0, 5, line)
        pdf.ln(5)

    # Save
    output = "/Users/vgopiraja/Documents/MY Applications/IntraTrading/IntraTrading_Daily_Guide.pdf"
    pdf.output(output)
    print(f"PDF generated: {output}")


if __name__ == "__main__":
    generate()
