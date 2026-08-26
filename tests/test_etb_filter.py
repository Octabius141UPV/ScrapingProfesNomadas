import unittest
from unittest.mock import AsyncMock, patch

from src.scrapers import scraper_educationposts as scraper_module
from src.bots.telegram_bot import format_etb_exclusion_notice


class SchoolNameExclusionTests(unittest.TestCase):
    def test_etb_requires_standalone_acronym_and_gaelscoil_remains_excluded(self):
        self.assertTrue(
            scraper_module.is_excluded_school_name(
                "Cork Education & Training Board (ETB)"
            )
        )
        self.assertTrue(scraper_module.is_excluded_school_name("ETB, Dublin"))
        self.assertFalse(scraper_module.is_excluded_school_name("Etbshire Primary School"))
        self.assertTrue(scraper_module.is_excluded_school_name("Scoil Gaelscoil Example"))

    def test_etb_notice_is_bounded_and_preserves_ignored_count(self):
        names = [f"ETB School {index} " + ("x" * 220) for index in range(40)]

        notice = format_etb_exclusion_notice(42, names)

        self.assertLessEqual(len(notice), 4096)
        self.assertIn("42 ofertas", notice)
        self.assertIn("nombres más", notice)


class EducationPostsEtbFilteringTests(unittest.IsolatedAsyncioTestCase):
    async def test_etb_listing_is_removed_before_detail_processing(self):
        scraper = scraper_module.EducationPosts(username=None, password=None)
        scraper._get_pages = AsyncMock(return_value=1)
        scraper._extract_urls_from_page = AsyncMock(
            return_value=[
                {
                    "url": "https://example.test/etb",
                    "school": "Cork Education & Training Board (ETB)",
                    "vacancy": "Teacher",
                },
                {
                    "url": "https://example.test/school",
                    "school": "Example Primary School",
                    "vacancy": "Teacher",
                },
            ]
        )
        scraper._offer_detail = AsyncMock(side_effect=lambda session, offer: offer)

        with patch.object(scraper_module.asyncio, "sleep", new=AsyncMock()):
            offers = await scraper.fetch_all(login_first=False)

        self.assertEqual(["Example Primary School"], [offer["school"] for offer in offers])
        scraper._offer_detail.assert_awaited_once()
        self.assertEqual(1, scraper.excluded_school_counts["ETB"])
        self.assertEqual(
            ["Cork Education & Training Board (ETB)"],
            scraper.excluded_school_names_by_reason["ETB"],
        )

    async def test_desktop_to_mobile_fallback_counts_same_etb_listing_once(self):
        html = """
        <table id="tblAdverts" class="d-none d-lg-table">
          <tbody>
            <tr data-href="/post/123">
              <td>123</td>
              <td><a href="/post/123">Cork Education &amp; Training Board (ETB)</a></td>
              <td>Teacher</td><td>Fixed</td><td>Cork</td><td>01/01/2030</td>
            </tr>
          </tbody>
        </table>
        <table class="mobileTable">
          <tr data-href="/post/123">
            <td>
              <div class="mobileRow"><span class="mobileLabel">School Name</span><span class="mobileData">Cork Education &amp; Training Board (ETB)</span></div>
              <div class="mobileRow"><span class="mobileLabel">Type of Vacancy</span><span class="mobileData">Teacher</span></div>
            </td>
          </tr>
        </table>
        """

        class FakeResponse:
            status = 200

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def text(self):
                return html

        class FakeSession:
            def get(self, *args, **kwargs):
                return FakeResponse()

        scraper = scraper_module.EducationPosts(username=None, password=None)
        with patch.object(scraper_module, "rand_sleep", new=AsyncMock()):
            offers = await scraper._extract_urls_from_page(FakeSession(), page=1)

        self.assertEqual([], offers)
        self.assertEqual(1, scraper.excluded_school_counts["ETB"])
        self.assertEqual(
            ["Cork Education & Training Board (ETB)"],
            scraper.excluded_school_names_by_reason["ETB"],
        )


if __name__ == "__main__":
    unittest.main()
