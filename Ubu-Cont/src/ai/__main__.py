"""
AI module entry point.

Allows running: python -m src.ai <command>
"""

import argparse
import sys
import os
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cmd_test(args):
    """Test OpenRouter connection."""
    from .openrouter_client import OpenRouterClient, OpenRouterConfig

    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("Error: OPENROUTER_API_KEY environment variable not set")
        return 1

    config = OpenRouterConfig(api_key=api_key)
    client = OpenRouterClient(config)

    print("Testing OpenRouter connection...")
    print(f"Model: {config.text_model}")

    try:
        response = client.chat(
            messages=[{"role": "user", "content": "Say 'Hello from OpenRouter!' in exactly those words."}],
            max_tokens=50
        )
        print(f"Response: {response}")
        print("\nConnection test successful!")
        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_analyze(args):
    """Analyze a screenshot."""
    from .openrouter_client import OpenRouterClient, OpenRouterConfig
    import base64

    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("Error: OPENROUTER_API_KEY environment variable not set")
        return 1

    if not os.path.exists(args.image):
        print(f"Error: Image not found: {args.image}")
        return 1

    config = OpenRouterConfig(api_key=api_key)
    client = OpenRouterClient(config)

    print(f"Analyzing: {args.image}")
    print(f"Prompt: {args.prompt}")

    try:
        # Read and encode image
        with open(args.image, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        # Determine mime type
        ext = args.image.lower().split('.')[-1]
        mime_types = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif'}
        mime_type = mime_types.get(ext, 'image/png')

        response = client.analyze_screen(
            screenshot_base64=image_data,
            prompt=args.prompt
        )

        print(f"\nAnalysis:\n{response}")
        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_find(args):
    """Find UI element in screenshot."""
    from .openrouter_client import OpenRouterClient, OpenRouterConfig
    import base64

    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("Error: OPENROUTER_API_KEY environment variable not set")
        return 1

    if not os.path.exists(args.image):
        print(f"Error: Image not found: {args.image}")
        return 1

    config = OpenRouterConfig(api_key=api_key)
    client = OpenRouterClient(config)

    print(f"Finding '{args.element}' in: {args.image}")

    try:
        with open(args.image, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        result = client.find_element(
            screenshot_base64=image_data,
            element_description=args.element
        )

        if result:
            print(f"\nElement found at: ({result['x']}, {result['y']})")
            print(f"Confidence: {result.get('confidence', 'N/A')}")
        else:
            print("\nElement not found")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_plan(args):
    """Get next action for a task."""
    from .openrouter_client import OpenRouterClient, OpenRouterConfig
    import base64

    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("Error: OPENROUTER_API_KEY environment variable not set")
        return 1

    config = OpenRouterConfig(api_key=api_key)
    client = OpenRouterClient(config)

    screenshot_base64 = None
    if args.image:
        if not os.path.exists(args.image):
            print(f"Error: Image not found: {args.image}")
            return 1
        with open(args.image, 'rb') as f:
            screenshot_base64 = base64.b64encode(f.read()).decode('utf-8')

    print(f"Task: {args.task}")
    print(f"Context: {args.context or 'None'}")

    try:
        result = client.decide_next_action(
            task=args.task,
            context=args.context or "",
            screenshot_base64=screenshot_base64
        )

        print(f"\nNext Action:")
        print(json.dumps(result, indent=2))
        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='ai',
        description='AI Module - OpenRouter integration for computer control'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Test command
    test_parser = subparsers.add_parser('test', help='Test OpenRouter connection')
    test_parser.set_defaults(func=cmd_test)

    # Analyze command
    ana_parser = subparsers.add_parser('analyze', help='Analyze a screenshot')
    ana_parser.add_argument('image', help='Path to screenshot')
    ana_parser.add_argument('-p', '--prompt', default='Describe what you see on this screen.',
                           help='Analysis prompt')
    ana_parser.set_defaults(func=cmd_analyze)

    # Find command
    find_parser = subparsers.add_parser('find', help='Find UI element')
    find_parser.add_argument('image', help='Path to screenshot')
    find_parser.add_argument('element', help='Element description')
    find_parser.set_defaults(func=cmd_find)

    # Plan command
    plan_parser = subparsers.add_parser('plan', help='Get next action for task')
    plan_parser.add_argument('task', help='Task to accomplish')
    plan_parser.add_argument('-c', '--context', help='Current context')
    plan_parser.add_argument('-i', '--image', help='Current screenshot')
    plan_parser.set_defaults(func=cmd_plan)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
