#!/usr/bin/env python3
"""
CLI tool for managing visual validation baselines.

Usage:
    python -m src.validation.cli register-all
    python -m src.validation.cli coverage linkedin_default
    python -m src.validation.cli create-baselines linkedin_default --from-run 5
    python -m src.validation.cli export linkedin_default ./exported_baselines/
"""

import argparse
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.validation.database import ValidationDatabase
from src.validation.workflow_parser import WorkflowParser
from src.validation.baseline_manager import BaselineManager

DB_PATH = "/home/ultra/proxmox-social/Ubu-Cont/workflow-validation/validation.db"
RECORDINGS_DIR = "/home/ultra/proxmox-social/Ubu-Cont/recordings"


def get_db():
    return ValidationDatabase(DB_PATH)


def get_parser():
    return WorkflowParser(RECORDINGS_DIR)


def cmd_register_all(args):
    """Register all workflows from recordings directory."""
    db = get_db()
    parser = get_parser()
    
    recordings_path = Path(RECORDINGS_DIR)
    count = 0
    
    for json_file in recordings_path.glob('*.json'):
        try:
            info = parser.parse_file(str(json_file))
            db.register_workflow(
                name=info.name,
                json_path=info.json_path,
                platform=info.platform,
                total_actions=info.total_actions,
                click_count=len(info.click_actions)
            )
            print(f"Registered: {info.name} ({len(info.click_actions)} clicks)")
            count += 1
        except Exception as e:
            print(f"Error registering {json_file}: {e}")
    
    print(f"\nTotal: {count} workflows registered")


def cmd_list_workflows(args):
    """List all registered workflows."""
    db = get_db()
    
    with db._get_connection() as conn:
        rows = conn.execute('SELECT * FROM workflows ORDER BY name').fetchall()
    
    if not rows:
        print("No workflows registered. Run: python -m src.validation.cli register-all")
        return
    
    print(f"{'Name':<30} {'Platform':<12} {'Actions':<10} {'Clicks':<10}")
    print("-" * 65)
    for row in rows:
        print(f"{row['name']:<30} {row['platform']:<12} {row['total_actions']:<10} {row['click_count']:<10}")


def cmd_coverage(args):
    """Show baseline coverage for a workflow."""
    db = get_db()
    parser = get_parser()
    
    workflow = db.get_workflow(args.workflow)
    if not workflow:
        print(f"Workflow not found: {args.workflow}")
        return
    
    try:
        info = parser.parse_file(workflow['json_path'])
    except Exception as e:
        print(f"Error parsing workflow: {e}")
        return
    
    baselines = db.get_baselines(workflow['id'])
    baseline_indices = {b['action_index'] for b in baselines}
    
    print(f"\nWorkflow: {args.workflow}")
    print(f"Platform: {workflow['platform']}")
    print(f"Total actions: {info.total_actions}")
    print(f"Click actions: {len(info.click_actions)}")
    print(f"Baselines exist: {len(baselines)}")
    print(f"Coverage: {len(baselines) / len(info.click_actions) * 100:.1f}%" if info.click_actions else "N/A")
    
    print(f"\nClick actions:")
    for click in info.click_actions:
        has_baseline = "✓" if click.index in baseline_indices else "✗"
        desc = click.description[:40] if click.description else ""
        print(f"  [{has_baseline}] {click.index:2d}: ({click.x:4d}, {click.y:4d}) {desc}")


def cmd_runs(args):
    """Show recent runs for a workflow."""
    db = get_db()
    
    workflow = db.get_workflow(args.workflow)
    if not workflow:
        print(f"Workflow not found: {args.workflow}")
        return
    
    runs = db.get_recent_runs(workflow['id'], limit=args.limit)
    
    if not runs:
        print(f"No runs found for {args.workflow}")
        return
    
    print(f"\nRecent runs for {args.workflow}:")
    print(f"{'ID':<6} {'Status':<20} {'Started':<20} {'Failure':<30}")
    print("-" * 80)
    
    for run in runs:
        failure = run['failure_reason'][:27] + "..." if run['failure_reason'] and len(run['failure_reason']) > 30 else (run['failure_reason'] or "")
        print(f"{run['id']:<6} {run['status']:<20} {run['started_at']:<20} {failure}")


def cmd_create_from_run(args):
    """Create baselines from a successful run."""
    db = get_db()
    parser = get_parser()
    
    workflow = db.get_workflow(args.workflow)
    if not workflow:
        print(f"Workflow not found: {args.workflow}")
        return
    
    screenshots = db.get_run_screenshots(args.run_id)
    if not screenshots:
        print(f"No screenshots found for run {args.run_id}")
        return
    
    info = parser.parse_file(workflow['json_path'])
    click_map = {c.index: c for c in info.click_actions}
    
    created = 0
    for ss in screenshots:
        action_index = ss['action_index']
        click = click_map.get(action_index)
        
        if click:
            db.save_baseline(
                workflow_id=workflow['id'],
                action_index=action_index,
                action_type=click.action_type,
                click_x=ss['click_x'],
                click_y=ss['click_y'],
                image_data=ss['captured_image'],
                description=click.description
            )
            created += 1
            print(f"Created baseline for action {action_index}")
    
    print(f"\nCreated {created} baselines from run {args.run_id}")


def cmd_export(args):
    """Export baselines to PNG files."""
    db = get_db()
    
    workflow = db.get_workflow(args.workflow)
    if not workflow:
        print(f"Workflow not found: {args.workflow}")
        return
    
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    baselines = db.get_baselines(workflow['id'])
    
    for baseline in baselines:
        filename = f"{args.workflow}_action{baseline['action_index']:02d}_{baseline['click_x']}x{baseline['click_y']}.png"
        filepath = output_path / filename
        
        with open(filepath, 'wb') as f:
            f.write(baseline['baseline_image'])
        print(f"Exported: {filename}")
    
    print(f"\nExported {len(baselines)} baselines to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Visual Validation CLI")
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # register-all
    subparsers.add_parser('register-all', help='Register all workflows from recordings')
    
    # list
    subparsers.add_parser('list', help='List all registered workflows')
    
    # coverage
    p = subparsers.add_parser('coverage', help='Show baseline coverage for a workflow')
    p.add_argument('workflow', help='Workflow name (e.g., linkedin_default)')
    
    # runs
    p = subparsers.add_parser('runs', help='Show recent runs for a workflow')
    p.add_argument('workflow', help='Workflow name')
    p.add_argument('--limit', type=int, default=10, help='Number of runs to show')
    
    # create-from-run
    p = subparsers.add_parser('create-from-run', help='Create baselines from a run')
    p.add_argument('workflow', help='Workflow name')
    p.add_argument('run_id', type=int, help='Run ID to create baselines from')
    
    # export
    p = subparsers.add_parser('export', help='Export baselines to PNG files')
    p.add_argument('workflow', help='Workflow name')
    p.add_argument('output_dir', help='Output directory')
    
    args = parser.parse_args()
    
    if args.command == 'register-all':
        cmd_register_all(args)
    elif args.command == 'list':
        cmd_list_workflows(args)
    elif args.command == 'coverage':
        cmd_coverage(args)
    elif args.command == 'runs':
        cmd_runs(args)
    elif args.command == 'create-from-run':
        cmd_create_from_run(args)
    elif args.command == 'export':
        cmd_export(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
