"""Test script to verify Instagram parser works correctly with sample data."""

import json
import os
import zipfile
import tempfile
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from instagram_parser import process_zip, ParseError


def create_test_zip(format_type: str = "new") -> str:
    """Create a test ZIP file with sample Instagram data."""
    tmp = tempfile.mktemp(suffix=".zip")

    with zipfile.ZipFile(tmp, "w") as zf:
        if format_type == "new":
            # New Instagram JSON format
            followers_data = [
                {
                    "title": "",
                    "media_list_data": [],
                    "string_list_data": [
                        {"href": "https://instagram.com/user1", "value": "user1", "timestamp": 1700000000},
                    ]
                },
                {
                    "title": "",
                    "media_list_data": [],
                    "string_list_data": [
                        {"href": "https://instagram.com/user2", "value": "user2", "timestamp": 1700000001},
                    ]
                },
                {
                    "title": "",
                    "media_list_data": [],
                    "string_list_data": [
                        {"href": "https://instagram.com/user3", "value": "user3", "timestamp": 1700000002},
                    ]
                },
                {
                    "title": "",
                    "media_list_data": [],
                    "string_list_data": [
                        {"href": "https://instagram.com/mutual1", "value": "mutual1", "timestamp": 1700000003},
                    ]
                },
                {
                    "title": "",
                    "media_list_data": [],
                    "string_list_data": [
                        {"href": "https://instagram.com/mutual2", "value": "mutual2", "timestamp": 1700000004},
                    ]
                },
            ]

            following_data = {
                "relationships_following": [
                    {
                        "title": "",
                        "media_list_data": [],
                        "string_list_data": [
                            {"href": "https://instagram.com/following1", "value": "following1", "timestamp": 1700000000},
                        ]
                    },
                    {
                        "title": "",
                        "media_list_data": [],
                        "string_list_data": [
                            {"href": "https://instagram.com/following2", "value": "following2", "timestamp": 1700000001},
                        ]
                    },
                    {
                        "title": "",
                        "media_list_data": [],
                        "string_list_data": [
                            {"href": "https://instagram.com/mutual1", "value": "mutual1", "timestamp": 1700000003},
                        ]
                    },
                    {
                        "title": "",
                        "media_list_data": [],
                        "string_list_data": [
                            {"href": "https://instagram.com/mutual2", "value": "mutual2", "timestamp": 1700000004},
                        ]
                    },
                ]
            }

            zf.writestr(
                "followers_and_following/followers_1.json",
                json.dumps(followers_data, indent=2)
            )
            zf.writestr(
                "followers_and_following/following.json",
                json.dumps(following_data, indent=2)
            )

    return tmp


def test_parser():
    print("=" * 50)
    print("Testing Instagram Parser")
    print("=" * 50)

    # Test new format
    print("\n📦 Test: New Instagram JSON format")
    zip_path = create_test_zip("new")
    try:
        result = process_zip(zip_path, 999999)
        print(f"  ✅ Followers:            {result['followers']}")
        print(f"  ✅ Following:            {result['following']}")
        print(f"  ✅ Mutual:               {result['mutual']}")
        print(f"  ✅ Not following back:    {result['not_following_back']}")
        print(f"  ✅ Not followed back:     {result['not_followed_back']}")
        print(f"  ✅ Mutual list:           {result['mutual_list']}")
        print(f"  ✅ Not following back:    {result['not_following_back_list']}")
        print(f"  ✅ Not followed back:     {result['not_followed_back_list']}")

        # Verify results
        assert result["followers"] == 5, f"Expected 5 followers, got {result['followers']}"
        assert result["following"] == 4, f"Expected 4 following, got {result['following']}"
        assert result["mutual"] == 2, f"Expected 2 mutual, got {result['mutual']}"
        assert result["not_following_back"] == 2, f"Expected 2 not following back"
        assert result["not_followed_back"] == 3, f"Expected 3 not followed back"
        print("\n  ✅ All assertions passed!")
    finally:
        os.unlink(zip_path)

    # Test HTML format support
    print("\n📦 Test: HTML format parsing")
    tmp = tempfile.mktemp(suffix=".zip")
    with zipfile.ZipFile(tmp, "w") as zf:
        zf.writestr(
            "followers_and_following/followers.html",
            """<html>
            <div><a href="https://www.instagram.com/user_a">user_a</a></div>
            <div><a href="https://www.instagram.com/user_b/">user_b</a></div>
            <div><a href="https://www.instagram.com/_u/user_c">user_c</a></div>
            </html>"""
        )
        zf.writestr(
            "followers_and_following/following.html",
            """<html>
            <div><a href="https://www.instagram.com/user_a">user_a</a></div>
            <div><a href="https://www.instagram.com/other_guy">other_guy</a></div>
            </html>"""
        )
    try:
        html_res = process_zip(tmp, 888888)
        print(f"  ✅ HTML Followers: {html_res['followers']}")
        print(f"  ✅ HTML Following: {html_res['following']}")
        print(f"  ✅ HTML Mutual:    {html_res['mutual']}")
        assert html_res["followers"] == 3
        assert html_res["following"] == 2
        assert html_res["mutual"] == 1
        assert "user_b" in html_res["not_followed_back_list"]
        assert "other_guy" in html_res["not_following_back_list"]
        print("  ✅ HTML parsing works perfectly!")
    finally:
        os.unlink(tmp)

    print("\n" + "=" * 50)
    print("All tests passed! ✅")
    print("=" * 50)


if __name__ == "__main__":
    test_parser()
