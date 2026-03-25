"""Tests for app/services/local_data.py shared utilities."""

import json
import os
import pytest
from decimal import Decimal
from datetime import datetime

from app.services.local_data import (
    decimal_default,
    convert_decimal,
    load_metadata_files_local,
    parse_timestamp_for_today,
    load_channels_from_local,
    is_timestamp_comment,
)


class TestDecimalDefault:
    def test_integer_decimal(self):
        assert decimal_default(Decimal('42')) == 42
        assert isinstance(decimal_default(Decimal('42')), int)

    def test_float_decimal(self):
        assert decimal_default(Decimal('3.14')) == 3.14
        assert isinstance(decimal_default(Decimal('3.14')), float)

    def test_non_decimal_raises(self):
        with pytest.raises(TypeError):
            decimal_default("not a decimal")

    def test_zero(self):
        assert decimal_default(Decimal('0')) == 0


class TestConvertDecimal:
    def test_decimal_value(self):
        assert convert_decimal(Decimal('10')) == 10

    def test_dict_with_decimals(self):
        result = convert_decimal({'a': Decimal('1'), 'b': Decimal('2.5')})
        assert result == {'a': 1, 'b': 2.5}

    def test_list_with_decimals(self):
        result = convert_decimal([Decimal('1'), Decimal('2')])
        assert result == [1, 2]

    def test_nested_structure(self):
        result = convert_decimal({'items': [{'val': Decimal('3')}]})
        assert result == {'items': [{'val': 3}]}

    def test_non_decimal_passthrough(self):
        assert convert_decimal("hello") == "hello"
        assert convert_decimal(42) == 42
        assert convert_decimal(None) is None


class TestLoadMetadataFilesLocal:
    def test_nonexistent_dir(self, tmp_path):
        result = load_metadata_files_local(str(tmp_path / 'nonexistent'))
        assert result == []

    def test_empty_dir(self, tmp_path):
        metadata_dir = tmp_path / 'metadata'
        metadata_dir.mkdir()
        result = load_metadata_files_local(str(metadata_dir))
        assert result == []

    def test_loads_json_files(self, tmp_path):
        platform_dir = tmp_path / 'youtube'
        platform_dir.mkdir()
        (platform_dir / 'item1.json').write_text(json.dumps({'id': '1', 'title': 'Test'}))
        (platform_dir / 'item2.json').write_text(json.dumps({'id': '2', 'title': 'Test2'}))
        (platform_dir / 'readme.txt').write_text('not json')

        result = load_metadata_files_local(str(tmp_path))
        assert len(result) == 2
        ids = {item['id'] for item in result}
        assert ids == {'1', '2'}

    def test_skips_invalid_json(self, tmp_path):
        platform_dir = tmp_path / 'dcinside'
        platform_dir.mkdir()
        (platform_dir / 'bad.json').write_text('not valid json{{{')
        (platform_dir / 'good.json').write_text(json.dumps({'id': 'ok'}))

        result = load_metadata_files_local(str(tmp_path))
        assert len(result) == 1
        assert result[0]['id'] == 'ok'


class TestParseTimestampForToday:
    def test_empty_string(self):
        assert parse_timestamp_for_today('', datetime.now()) is False

    def test_none(self):
        assert parse_timestamp_for_today(None, datetime.now()) is False

    def test_iso_format_today(self):
        now = datetime.now()
        today_start = datetime(now.year, now.month, now.day)
        ts = now.isoformat()
        assert parse_timestamp_for_today(ts, today_start) is True

    def test_iso_format_yesterday(self):
        now = datetime.now()
        today_start = datetime(now.year, now.month, now.day)
        yesterday = datetime(now.year, now.month, now.day, 0, 0, 0)
        from datetime import timedelta
        old_ts = (yesterday - timedelta(days=1)).isoformat()
        assert parse_timestamp_for_today(old_ts, today_start) is False

    def test_invalid_format(self):
        assert parse_timestamp_for_today('not-a-date', datetime.now()) is False

    def test_utc_z_suffix(self):
        now = datetime.now()
        today_start = datetime(now.year, now.month, now.day)
        ts = now.isoformat() + 'Z'
        # Should handle Z suffix gracefully
        result = parse_timestamp_for_today(ts, today_start)
        assert isinstance(result, bool)


class TestLoadChannelsFromLocal:
    def test_nonexistent_dir(self, tmp_path):
        result = load_channels_from_local(str(tmp_path / 'nonexistent'))
        assert result == []

    def test_empty_dir(self, tmp_path):
        yt_dir = tmp_path / 'youtube'
        yt_dir.mkdir()
        result = load_channels_from_local(str(yt_dir))
        assert result == []

    def test_loads_channel_data(self, tmp_path):
        channels_dir = tmp_path / 'channels'
        channels_dir.mkdir()
        data = {
            'channel_handle': '@testchannel',
            'channel_title': 'Test Channel',
            'videos': [
                {'title': 'V1', 'comments': 10},
                {'title': 'V2', 'comment_count': 5},
            ],
            'last_updated': '2026-03-25',
        }
        (channels_dir / 'testchannel.json').write_text(json.dumps(data))

        result = load_channels_from_local(str(tmp_path))
        assert len(result) == 1
        assert result[0]['channel'] == '@testchannel'
        assert result[0]['channel_title'] == 'Test Channel'
        assert result[0]['videos_analyzed'] == 2
        assert result[0]['total_comments'] == 15

    def test_deduplicates_channels(self, tmp_path):
        channels_dir = tmp_path / 'channels'
        channels_dir.mkdir()
        data = {'channel_handle': '@same', 'channel_title': 'Same', 'videos': []}
        (channels_dir / 'a.json').write_text(json.dumps(data))
        (channels_dir / 'b.json').write_text(json.dumps(data))

        result = load_channels_from_local(str(tmp_path))
        assert len(result) == 1


class TestIsTimestampComment:
    def test_empty(self):
        assert is_timestamp_comment('') is False
        assert is_timestamp_comment(None) is False

    def test_normal_comment(self):
        assert is_timestamp_comment('Great video!') is False

    def test_song_list(self):
        text = "00:00 Song A\n02:30 Song B\n05:15 Song C"
        assert is_timestamp_comment(text) is True

    def test_chapter_list(self):
        text = "0:00 Intro\n1:30 Main topic\n5:00 Conclusion\n8:00 Outro"
        assert is_timestamp_comment(text) is True

    def test_few_timestamps(self):
        text = "Check at 1:30 and 2:00"
        assert is_timestamp_comment(text) is False

    def test_single_line(self):
        text = "01:00:00 02:00:00 03:00:00"
        assert is_timestamp_comment(text) is True
