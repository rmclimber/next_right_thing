import unittest

import feedparser

from nrt_backend.lambdas.rss_fetch import handler, podcast


JOB = {"user_id": "user", "content_source_id": "source", "url": "https://example.com/feed"}
DISCOVERED_AT = "2026-11-18T12:00:00Z"
AUDIO_URL = "https://example.com/episode.mp3"


class PodcastParsingTests(unittest.TestCase):
    def test_itunes_duration_formats_round_up_to_positive_minutes(self):
        for value, expected in [("1", 1), ("60", 1), ("61", 2), ("00:59", 1),
                                ("12:34", 13), ("125:00", 125), ("1:02:03", 63),
                                (" 00:01:00 ", 1), ("128849018820", 2147483647)]:
            with self.subTest(value=value):
                self.assertEqual(podcast.duration_minutes({"itunes_duration": value}), expected)

    def test_missing_malformed_and_out_of_range_duration_is_unknown(self):
        for value in (None, "", "0", "00:00", "-1", "1.5", "NaN", "1:60", "1:60:00",
                      "1:00:60", "1:2:3:4", "128849018821", "9" * 5000, True, 42):
            with self.subTest(value=str(value)[:30]):
                self.assertIsNone(podcast.duration_minutes({"itunes_duration": value}))

    def test_first_usable_audio_enclosure_wins(self):
        entry = {"enclosures": [None, {"type": None},
                                {"type": "video/mp4", "href": "https://example.com/video"},
                                {"type": "audio/mpeg", "href": "javascript:alert(1)"},
                                {"type": "audio/mpeg", "href": "https://[broken"},
                                {"type": "audio/mpeg", "href": "https://example.com/bad url"},
                                {"type": "Audio/Mpeg; charset=utf-8", "href": AUDIO_URL},
                                {"type": "audio/ogg", "href": "https://example.com/other"}]}
        self.assertEqual(podcast.audio_enclosure_url(entry), AUDIO_URL)

    def test_invalid_enclosure_authority_does_not_override_later_valid_audio(self):
        for invalid_url in ("https://example.com:bad/audio.mp3",
                            "https://example.com:-1/audio.mp3",
                            "https://example.com:65536/audio.mp3",
                            "https://example.com:99999/audio.mp3",
                            "https://:443/audio.mp3",
                            "https://user@:443/audio.mp3"):
            with self.subTest(url=invalid_url):
                parsed = feedparser.parse(f'''<rss version="2.0"><channel><title>Podcast</title>
                  <item><title>Episode</title><guid isPermaLink="false">episode-1</guid>
                  <enclosure url="{invalid_url}" type="audio/mpeg" length="100"/>
                  <enclosure url="{AUDIO_URL}" type="audio/mpeg" length="100"/>
                  </item></channel></rss>''')
                item = handler._normalize_entry(JOB, parsed.entries[0], DISCOVERED_AT)
                self.assertEqual(item["url"], AUDIO_URL)
                self.assertEqual(item["content_type"], "podcast_episode")
                self.assertEqual(item["external_id"], "episode-1")
                entry = {"title": "Episode", "enclosures": [{"type": "audio/mpeg", "href": invalid_url}]}
                self.assertIsNone(podcast.audio_enclosure_url(entry))
                self.assertIsNone(handler._normalize_entry(JOB, entry, DISCOVERED_AT))

    def test_valid_enclosure_hosts_and_ports_are_preserved(self):
        for url in (AUDIO_URL, "http://example.com:8080/audio.mp3",
                    "https://example.com:443/audio.mp3", "https://example.com:65535/audio.mp3",
                    "https://[2001:db8::1]:8443/audio.mp3"):
            with self.subTest(url=url):
                self.assertEqual(podcast.audio_enclosure_url({
                    "enclosures": [{"type": "audio/mpeg", "href": url}],
                }), url)

    def test_guid_then_permalink_then_audio_identity_and_listening_url(self):
        base = {"title": "Episode", "enclosures": [{"type": "audio/mpeg", "href": AUDIO_URL}]}
        for extra, identity in [({"id": "guid", "link": "https://example.com/page"}, "guid"),
                                ({"link": "https://example.com/page"}, "https://example.com/page"),
                                ({}, AUDIO_URL)]:
            with self.subTest(extra=extra):
                item = handler._normalize_entry(JOB, {**base, **extra}, DISCOVERED_AT)
                self.assertEqual(item["external_id"], identity)
                self.assertEqual(item["url"], AUDIO_URL)
                self.assertEqual(item["content_type"], "podcast_episode")
                self.assertIsNone(item["duration_minutes"])
                self.assertIsNone(item["summary"])
                self.assertIsNone(item["published_at"])

    def test_real_rss_itunes_and_content_namespaces(self):
        parsed = feedparser.parse(b'''<rss version="2.0"
          xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
          xmlns:content="http://purl.org/rss/1.0/modules/content/">
          <channel><title>Professional podcast</title><link>https://example.com</link><description>Show</description>
          <item><title>Episode</title><guid isPermaLink="false">episode-1</guid>
          <content:encoded><![CDATA[<p>Episode description</p>]]></content:encoded>
          <pubDate>Wed, 18 Nov 2026 10:00:00 GMT</pubDate><itunes:duration>12:34</itunes:duration>
          <enclosure url="https://example.com/episode.mp3" type="audio/mpeg" length="100"/>
          </item></channel></rss>''')
        self.assertFalse(parsed.bozo)
        item = handler._normalize_entry(JOB, parsed.entries[0], DISCOVERED_AT)
        self.assertEqual(item["summary"], "<p>Episode description</p>")
        self.assertEqual(item["published_at"], "2026-11-18T10:00:00Z")
        self.assertEqual(item["duration_minutes"], 13)

    def test_description_fallbacks(self):
        for entry, expected in [({"summary": " First ", "subtitle": "Second"}, "First"),
                                ({"itunes_summary": "Details"}, "Details"),
                                ({"summary": " ", "subtitle": "Short description"}, "Short description"),
                                ({"content": [None, {"value": "Full description"}]}, "Full description")]:
            self.assertEqual(podcast.description(entry), expected)

    def test_bad_optional_metadata_does_not_block_other_entries(self):
        base = {"title": "Episode", "enclosures": [{"type": "audio/mpeg", "href": AUDIO_URL}]}
        entries = [{**base, "published_parsed": (2026, 99, 99), "published": "bad date",
                    "summary": 42, "itunes_duration": "bad duration"},
                   {**base, "title": ""},
                   {"title": "Article", "link": "https://example.com/post", "itunes_duration": "600"}]
        items, skipped = handler._normalized_items(JOB, entries, DISCOVERED_AT)
        self.assertEqual(skipped, 1)
        self.assertEqual(len(items), 2)
        self.assertIsNone(items[0]["published_at"])
        self.assertIsNone(items[0]["duration_minutes"])
        self.assertNotIn("content_type", items[1])
        self.assertNotIn("duration_minutes", items[1])

    def test_non_audio_or_unusable_enclosures_preserve_article_behavior(self):
        for enclosure in [{"type": "video/mp4", "href": AUDIO_URL},
                          {"href": AUDIO_URL}, {"type": "audio/mpeg", "href": "ftp://example.com/a"}]:
            item = handler._normalize_entry(JOB, {"title": "Article", "link": "https://example.com/post",
                                                  "enclosures": [enclosure]}, DISCOVERED_AT)
            self.assertNotIn("content_type", item)
            self.assertIsNone(handler._normalize_entry(JOB, {"title": "Unusable", "enclosures": [enclosure]}, DISCOVERED_AT))
