from services.ingest import screener
from services.research import grounded
from bs4 import BeautifulSoup

HTML = """<section id="quarters"><table><thead><tr><th></th><th>Jun 2026</th><th>Sep 2026</th></tr></thead><tbody>
<tr><td>Sales +</td><td>1,000</td><td>1,100</td></tr><tr><td>Net Profit +</td><td>150</td><td>165</td></tr>
<tr><td>OPM %</td><td>20%</td><td>21%</td></tr></tbody></table></section>
<section id="documents"><div class="concalls"><ul><li>Oct 2026 <a href="https://x/t1.pdf">Transcript</a> <a href="https://x/p.pdf">PPT</a></li>
<li>Jul 2026 <a href="https://x/t2.pdf">Transcript</a></li></ul></div></section>"""          # made-up page in screener's layout


def test_screener_tables_and_periods():
    soup = BeautifulSoup(HTML, "html.parser")
    f = {(x.metric, x.period): x.value for x in screener.table(soup, "quarters", "TEST", "consolidated", "u", True)}
    assert f == {("revenue", "Q1_FY27"): 1000, ("revenue", "Q2_FY27"): 1100, ("pat", "Q1_FY27"): 150, ("pat", "Q2_FY27"): 165}


def test_transcript_links_and_call_period():
    soup = BeautifulSoup(HTML, "html.parser")
    assert [t["url"] for t in screener.transcripts(soup)] == ["https://x/t1.pdf", "https://x/t2.pdf"]
    assert screener.call_period("Oct 2026") == "Q2_FY27" and screener.call_period("May 2026") == "Q4_FY26"


def test_a_quote_that_is_not_in_the_document_is_dropped():           # grounding
    pages = ["Welcome to the call.", "We expect revenue growth of 8 to 10 percent in fiscal 2027, in constant currency."]
    assert grounded({"quote": "We expect revenue growth of 8 to 10 percent in fiscal 2027", "page": 1}, pages) == 2
    assert grounded({"quote": "We will double revenue by fiscal 2028 for sure, no doubt", "page": 2}, pages) is None


def test_only_pages_with_forward_looking_numbers_are_sent():
    from services.research import relevant_pages
    pages = ["Good evening and welcome to the call.", "Revenue was 1,000 crore last quarter.",
             "We expect revenue growth of 8% to 10% in FY27 and our guidance is unchanged.", "Thank you all."]
    assert relevant_pages(pages) == [2]
    big = ["We expect 10% growth next year. " * 400] * 5
    assert len(relevant_pages(big, budget=30_000)) == 2          # stays within the budget
