#!/usr/bin/env python3
"""Test script to verify the message content extraction fix."""

import asyncio
import sys
import os

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from asksage_proxy.endpoints.chat import extract_text_from_content, transform_openai_to_asksage


def test_extract_text_from_content():
    """Test the extract_text_from_content function with various inputs."""
    print("Testing extract_text_from_content function...")
    
    # Test 1: Simple string content
    simple_content = "Hello, world!"
    result = extract_text_from_content(simple_content)
    print(f"Test 1 - Simple string: '{simple_content}' -> '{result}'")
    assert result == "Hello, world!"
    
    # Test 2: List with single text content part
    single_part_content = [{'type': 'text', 'text': 'Single part message'}]
    result = extract_text_from_content(single_part_content)
    print(f"Test 2 - Single part: {single_part_content} -> '{result}'")
    assert result == "Single part message"
    
    # Test 3: List with multiple text content parts (the problematic case)
    multi_part_content = [
        {'type': 'text', 'text': 'First part of the message'},
        {'type': 'text', 'text': 'Second part of the message'}
    ]
    result = extract_text_from_content(multi_part_content)
    print(f"Test 3 - Multi part: {multi_part_content} -> '{result}'")
    expected = "First part of the message\nSecond part of the message"
    assert result == expected
    
    # Test 4: Empty content
    empty_content = ""
    result = extract_text_from_content(empty_content)
    print(f"Test 4 - Empty string: '{empty_content}' -> '{result}'")
    assert result == ""
    
    # Test 5: Empty list
    empty_list = []
    result = extract_text_from_content(empty_list)
    print(f"Test 5 - Empty list: {empty_list} -> '{result}'")
    assert result == ""
    
    # Test 6: List with non-text content parts (should be ignored)
    mixed_content = [
        {'type': 'text', 'text': 'Text content'},
        {'type': 'image', 'url': 'https://example.com/image.jpg'},
        {'type': 'text', 'text': 'More text content'}
    ]
    result = extract_text_from_content(mixed_content)
    print(f"Test 6 - Mixed content: {mixed_content} -> '{result}'")
    expected = "Text content\nMore text content"
    assert result == expected
    
    print("✅ All extract_text_from_content tests passed!")


async def test_transform_openai_to_asksage():
    """Test the transform_openai_to_asksage function with multi-part content."""
    print("\nTesting transform_openai_to_asksage function...")
    
    # Test case: OpenAI request with multi-part content (the problematic case)
    openai_request = {
        "model": "gpt-4",
        "messages": [
            {
                "role": "user",
                "content": [
                    {'type': 'text', 'text': '<task>\nplease edit the readme\n\n> Not OpenAI Compatible\n\nThese endpoints interact directly with the AskSage API and do not convert responses to OpenAI\'s format:\n\n    /: Root endpoint with API information.\n    /health: Health check endpoint. Returns 200 OK if the server is running.\n> \n\n\nthese are not directly querying against asksage\n\nit\'s endpoints I defined for our proxy server\nalso include /version\n</task>'},
                    {'type': 'text', 'text': '<environment_details>\n# VSCode Visible Files\nREADME_en.md\n\n# VSCode Open Tabs\nsrc/asksage_proxy/endpoints/chat.py\n</environment_details>'}
                ]
            }
        ]
    }
    
    result = await transform_openai_to_asksage(openai_request)
    
    print(f"Input messages: {openai_request['messages']}")
    print(f"Transformed message: '{result['message']}'")
    
    # Verify that both parts are combined
    expected_parts = [
        '<task>\nplease edit the readme',
        '<environment_details>\n# VSCode Visible Files\nREADME_en.md'
    ]
    
    for part in expected_parts:
        assert part in result['message'], f"Expected part '{part}' not found in result message"
    
    # Verify other fields are preserved
    assert result['model'] == 'gpt-4'
    assert 'temperature' in result
    assert 'persona' in result
    assert 'dataset' in result
    
    print("✅ transform_openai_to_asksage test passed!")


async def main():
    """Run all tests."""
    print("Running message content extraction fix tests...\n")
    
    test_extract_text_from_content()
    await test_transform_openai_to_asksage()
    
    print("\n🎉 All tests passed! The fix is working correctly.")
    print("\nThe fix now properly handles OpenAI messages with multiple content parts")
    print("by extracting text from each part and combining them into a single message")
    print("that AskSage can understand.")


if __name__ == "__main__":
    asyncio.run(main())