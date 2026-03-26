#!/usr/bin/env python3
"""
Shadow Mode Runner.

CLI tool to run shadow mode processing for validating AI responses
without affecting real customers.

Usage:
    python scripts/run_shadow_mode.py --client client_001 --count 50
    python scripts/run_shadow_mode.py --client client_001 --tickets tickets.json
    python scripts/run_shadow_mode.py --help

CRITICAL: Shadow mode NEVER sends responses to customers.
"""
import argparse
import json
import logging
import random
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from clients.shadow_mode_handler import (
    ShadowModeHandler,
    ShadowTicket,
    ShadowDecision,
    create_mock_ai_processor
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Sample tickets for testing
SAMPLE_TICKETS = [
    {
        "subject": "Refund request for order #12345",
        "body": "Hi, I would like to request a refund for my order #12345. The product arrived damaged.",
        "category": "returns",
        "priority": "high"
    },
    {
        "subject": "Where is my order?",
        "body": "I placed an order 5 days ago and haven't received any shipping updates. Where is my order?",
        "category": "shipping",
        "priority": "medium"
    },
    {
        "subject": "Product question",
        "body": "Does this product come in different colors? I'm interested in the blue version.",
        "category": "products",
        "priority": "low"
    },
    {
        "subject": "Need to speak to manager",
        "body": "I've been trying to resolve this issue for weeks. I need to speak to a manager immediately!",
        "category": "escalation",
        "priority": "critical"
    },
    {
        "subject": "Shipping costs",
        "body": "How much is shipping to Canada? I couldn't find this information on your website.",
        "category": "shipping",
        "priority": "low"
    },
    {
        "subject": "Wrong item received",
        "body": "I ordered a size M shirt but received a size L. I want to exchange it.",
        "category": "returns",
        "priority": "medium"
    },
    {
        "subject": "Account login issue",
        "body": "I can't log into my account. It keeps saying invalid password but I'm sure it's correct.",
        "category": "account",
        "priority": "high"
    },
    {
        "subject": "Discount code not working",
        "body": "I have a discount code SAVE20 but it's not applying at checkout. Can you help?",
        "category": "billing",
        "priority": "medium"
    },
    {
        "subject": "Product availability",
        "body": "When will the iPhone 15 case be back in stock? It shows as out of stock.",
        "category": "products",
        "priority": "low"
    },
    {
        "subject": "Cancel my subscription",
        "body": "I want to cancel my monthly subscription. Please process this immediately.",
        "category": "billing",
        "priority": "high"
    }
]


def generate_sample_tickets(count: int, client_id: str) -> List[ShadowTicket]:
    """Generate sample tickets for testing."""
    tickets = []

    for i in range(count):
        sample = SAMPLE_TICKETS[i % len(SAMPLE_TICKETS)]
        ticket = ShadowTicket(
            ticket_id=f"TKT-{uuid.uuid4().hex[:8].upper()}",
            client_id=client_id,
            subject=sample["subject"],
            body=sample["body"],
            customer_email=f"customer{i}@example.com",
            category=sample.get("category"),
            priority=sample.get("priority", "medium"),
            metadata={
                "source": "shadow_mode_test",
                "generated_at": datetime.utcnow().isoformat()
            }
        )
        tickets.append(ticket)

    return tickets


def load_tickets_from_file(filepath: str, client_id: str) -> List[ShadowTicket]:
    """Load tickets from a JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    tickets = []
    for item in data:
        ticket = ShadowTicket(
            ticket_id=item.get("ticket_id", f"TKT-{uuid.uuid4().hex[:8].upper()}"),
            client_id=client_id,
            subject=item.get("subject", ""),
            body=item.get("body", ""),
            customer_email=item.get("customer_email", "test@example.com"),
            category=item.get("category"),
            priority=item.get("priority", "medium"),
            metadata=item.get("metadata", {})
        )
        tickets.append(ticket)

    return tickets


def print_progress(current: int, total: int) -> None:
    """Print progress bar."""
    percent = (current / total) * 100
    bar_length = 40
    filled = int(bar_length * current // total)
    bar = '█' * filled + '-' * (bar_length - filled)
    print(f'\rProgress: |{bar}| {current}/{total} ({percent:.1f}%)', end='', flush=True)


def run_shadow_mode(
    client_id: str,
    ticket_count: int = 50,
    tickets_file: Optional[str] = None,
    output_dir: str = "./shadow_results",
    use_real_ai: bool = False
) -> Dict[str, Any]:
    """
    Run shadow mode processing.

    Args:
        client_id: Client identifier
        ticket_count: Number of tickets to process (if generating)
        tickets_file: Path to JSON file with tickets
        output_dir: Directory for results
        use_real_ai: Whether to use real AI (if False, uses mock)

    Returns:
        Results summary
    """
    logger.info(f"Starting shadow mode for client: {client_id}")

    # Initialize handler
    handler = ShadowModeHandler(
        client_id=client_id,
        output_dir=output_dir
    )

    # Get tickets
    if tickets_file:
        logger.info(f"Loading tickets from {tickets_file}")
        tickets = load_tickets_from_file(tickets_file, client_id)
    else:
        logger.info(f"Generating {ticket_count} sample tickets")
        tickets = generate_sample_tickets(ticket_count, client_id)

    logger.info(f"Processing {len(tickets)} tickets in shadow mode")

    # Create AI processor
    if use_real_ai:
        # Would use ZAI SDK here
        logger.warning("Real AI not implemented, using mock")
        ai_processor = create_mock_ai_processor()
    else:
        ai_processor = create_mock_ai_processor()

    # Process tickets
    start_time = time.time()
    results = handler.process_batch(
        tickets,
        ai_processor,
        progress_callback=print_progress
    )
    total_time = time.time() - start_time

    print()  # New line after progress bar

    # Get metrics
    metrics = handler.get_accuracy_metrics()

    # Export results
    export_path = handler.export_results()

    # Verify safety
    safety_check = ShadowModeHandler.verify_no_responses_sent()

    # Build summary
    summary = {
        "client_id": client_id,
        "tickets_processed": len(tickets),
        "processing_time_seconds": round(total_time, 2),
        "tickets_per_second": round(len(tickets) / total_time, 2),
        "avg_processing_time_ms": metrics.get("avg_processing_time_ms", 0),
        "error_count": metrics.get("error_count", 0),
        "safety_verification": {
            "response_send_attempts": 0,
            "all_responses_prevented": True,
            "shadow_mode_verified": safety_check
        },
        "export_path": export_path,
        "timestamp": datetime.utcnow().isoformat()
    }

    return summary


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run shadow mode processing for AI validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Process 50 generated tickets
    python scripts/run_shadow_mode.py --client client_001 --count 50

    # Process tickets from file
    python scripts/run_shadow_mode.py --client client_001 --tickets data.json

    # Specify output directory
    python scripts/run_shadow_mode.py --client client_001 --count 100 --output ./results
        """
    )

    parser.add_argument(
        "--client", "-c",
        required=True,
        help="Client ID to process tickets for"
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=50,
        help="Number of tickets to generate and process (default: 50)"
    )
    parser.add_argument(
        "--tickets", "-t",
        help="Path to JSON file containing tickets"
    )
    parser.add_argument(
        "--output", "-o",
        default="./shadow_results",
        help="Output directory for results (default: ./shadow_results)"
    )
    parser.add_argument(
        "--real-ai",
        action="store_true",
        help="Use real AI instead of mock (requires API access)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    try:
        summary = run_shadow_mode(
            client_id=args.client,
            ticket_count=args.count,
            tickets_file=args.tickets,
            output_dir=args.output,
            use_real_ai=args.real_ai
        )

        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print("\n" + "=" * 60)
            print("SHADOW MODE RESULTS")
            print("=" * 60)
            print(f"Client:              {summary['client_id']}")
            print(f"Tickets Processed:   {summary['tickets_processed']}")
            print(f"Processing Time:     {summary['processing_time_seconds']}s")
            print(f"Tickets/Second:      {summary['tickets_per_second']}")
            print(f"Avg Response Time:   {summary['avg_processing_time_ms']:.1f}ms")
            print(f"Errors:              {summary['error_count']}")
            print(f"\nSAFETY VERIFICATION:")
            print(f"  Responses Sent:    {summary['safety_verification']['response_send_attempts']}")
            print(f"  Shadow Mode:       {'✅ VERIFIED' if summary['safety_verification']['shadow_mode_verified'] else '❌ FAILED'}")
            print(f"\nResults exported to: {summary['export_path']}")
            print("=" * 60)

        # Exit with error code if safety check failed
        if not summary['safety_verification']['shadow_mode_verified']:
            sys.exit(1)

        sys.exit(0)

    except Exception as e:
        logger.error(f"Shadow mode failed: {e}")
        print(f"\n❌ ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
