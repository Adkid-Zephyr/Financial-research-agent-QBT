import asyncio
from datetime import date

from futures_research.main import run_research


if __name__ == "__main__":
    state = asyncio.run(run_research(symbol="CF", target_date=date.today()))
    if state.final_report is not None:
        print(state.final_report.content)
