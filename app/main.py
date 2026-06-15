from __future__ import annotations

import argparse
import sys

from .feishu import FeishuClient, FeishuConfigError
from .logging_utils import setup_logging
from .profiles import DEFAULT_PROFILE_ID, ProfileNotFoundError
from .runner import (
    backfill_feishu,
    html_report_path,
    reset_pilot_sync_state,
    run_once,
    run_pilot_notice_whitelist,
    structured_preview_report_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TenderRadarLite local tender monitoring")
    parser.add_argument("--init-feishu-schema", action="store_true", help="Initialize Feishu schema")
    parser.add_argument("--init-feishu-fields", action="store_true", help="Initialize or backfill required Feishu fields")
    parser.add_argument("--test-feishu-write", action="store_true", help="Write one Feishu test record")
    parser.add_argument("--test-webhook", action="store_true", help="Send one Feishu webhook test message")
    parser.add_argument("--list-feishu-chats", action="store_true", help="List visible Feishu chats for app bot mode")
    parser.add_argument("--test-feishu-bot", action="store_true", help="Send one Feishu bot test message with current bot mode")
    parser.add_argument("--backfill-feishu", action="store_true", help="Backfill matching SQLite history to Feishu")
    parser.add_argument("--reset-pilot-sync-state", action="store_true", help="Reset pilot Feishu sync state for whitelist notices")
    parser.add_argument("--local-only", action="store_true", help="Fetch and dedupe locally without Feishu")
    parser.add_argument(
        "--local-structured-preview",
        action="store_true",
        help="Fetch new sources and generate local structured preview without Feishu",
    )
    parser.add_argument(
        "--local-html",
        action="store_true",
        help="Fetch new sources and generate a local HTML report without Feishu",
    )
    parser.add_argument(
        "--ai-analysis",
        action="store_true",
        help="Optionally generate AI-assisted explanations for DIRECT/WATCHLIST items in local HTML mode",
    )
    parser.add_argument(
        "--ai-analysis-limit",
        type=int,
        help="Maximum DIRECT/WATCHLIST items to analyze when --ai-analysis is enabled",
    )
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE_ID,
        help=f"Industry profile to use for local classification (default: {DEFAULT_PROFILE_ID})",
    )
    parser.add_argument("--pilot-notice-ids-file", help="Run notice_id whitelist preview or execute flow")
    parser.add_argument("--dry-run", action="store_true", help="Preview whitelist notices without side effects")
    parser.add_argument("--execute", action="store_true", help="Execute whitelist notices with real side effects")
    return parser


def _print_env_status(client: FeishuClient) -> None:
    for line in client.get_env_status_lines():
        print(line)


def _print_feishu_chats(chats) -> None:
    if not chats:
        print("no chats found")
        return
    for item in chats:
        print(f"name={item.get('name', '')}, chat_id={item.get('chat_id', '')}")


def _print_run_results(results) -> None:
    print("run completed")
    total_feishu = 0
    total_webhook = 0
    for item in results:
        total_feishu += item.feishu_written_count
        total_webhook += item.webhook_sent_count
        print(
            f"{item.source_name}: fetched={item.fetched_count}, inserted={item.inserted_count}, "
            f"duplicates={item.duplicate_count}, pushed={item.pushed_count}, "
            f"pages_scanned={item.pages_scanned}, page_size={item.page_size}, "
            f"detail_success={item.detail_success_count}, real_notice={item.real_notice_count}, "
            f"skipped={item.skipped_count}, direct={item.direct_count}, watchlist={item.watchlist_count}, "
            f"exclude={item.exclude_count}, feishu_written={item.feishu_written_count}, "
            f"webhook_sent={item.webhook_sent_count}, error_count={item.error_count}, "
            f"latest_site_publish_time={item.latest_site_publish_time}, "
            f"latest_db_publish_time={item.latest_db_publish_time}, fetch_failed={'yes' if item.fetch_failed else 'no'}"
        )
    print(f"totals: feishu_written={total_feishu}, webhook_sent={total_webhook}")


def _print_pilot_notice_whitelist_result(result) -> None:
    mode = "execute" if result.execute else "dry-run"
    print(f"pilot_notice_whitelist: mode={mode}")
    for item in result.records:
        print(
            f"notice_id={item.notice_id}, section_id={item.section_id}, project_name={item.project_name}, "
            f"section_name={item.section_name}, notice_type={item.notice_type}, display_status={item.display_status}, "
            f"publish_time={item.publish_time}, lead_tier={item.lead_tier}, "
            f"exists_in_sqlite={'yes' if item.exists_in_sqlite else 'no'}, "
            f"match_status={item.match_status}, "
            f"legacy_current_dedupe_key={item.legacy_current_dedupe_key}, "
            f"legacy_current_notice_id={item.legacy_current_notice_id}, "
            f"legacy_upgrade_dedupe_key={item.legacy_upgrade_dedupe_key}, "
            f"will_insert_sqlite={'yes' if item.will_insert_sqlite else 'no'}, "
            f"will_upgrade_legacy={'yes' if item.will_upgrade_legacy else 'no'}, "
            f"will_write_feishu={'yes' if item.will_write_feishu else 'no'}, "
            f"will_send_bot={'yes' if item.will_send_bot else 'no'}, "
            f"employee_readable_url={item.employee_readable_url}, dedupe_key={item.dedupe_key}, "
            f"lead_reason={item.lead_reason}"
        )
    print(f"whitelist_total={result.notice_ids_total}")
    print(f"matched_count={result.matched_count}")
    print(f"missing_notice_ids={','.join(result.missing_notice_ids) if result.missing_notice_ids else 'none'}")
    print(f"existing_count={result.existing_count}")
    print(f"sqlite_inserted={result.sqlite_inserted_count}")
    print(f"feishu_written={result.feishu_written_count}")
    print(f"webhook_sent={result.webhook_sent_count}")
    print(f"direct={result.direct_count}, watchlist={result.watchlist_count}, exclude={result.exclude_count}")
    print(f"non_whitelist_scanned={result.non_whitelist_scanned_count}")
    print(f"non_whitelist_written={result.non_whitelist_written_count}")
    print(f"bot_notice_ids={','.join(result.bot_notice_ids) if result.bot_notice_ids else 'none'}")


def _return_code_for_run(results, logger) -> int:
    if results and all(item.fetch_failed for item in results):
        logger.error("all enabled sources failed to fetch")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logger = setup_logging()

    selected = [
        args.init_feishu_schema,
        args.init_feishu_fields,
        args.test_feishu_write,
        args.test_webhook,
        args.list_feishu_chats,
        args.test_feishu_bot,
        args.backfill_feishu,
        args.reset_pilot_sync_state,
        args.local_only,
        args.local_structured_preview,
        args.local_html,
    ]
    if sum(1 for flag in selected if flag) > 1:
        parser.error("only one primary command may run at a time")
    if args.dry_run and args.execute:
        parser.error("--dry-run and --execute cannot be combined")
    if (args.dry_run or args.execute) and not args.pilot_notice_ids_file:
        parser.error("--dry-run/--execute require --pilot-notice-ids-file")
    if args.backfill_feishu and (args.dry_run or args.execute):
        parser.error("--backfill-feishu cannot be combined with --dry-run/--execute")
    if args.reset_pilot_sync_state and (args.dry_run or args.execute):
        parser.error("--reset-pilot-sync-state cannot be combined with --dry-run/--execute")
    selected_without_pilot_file = [
        args.init_feishu_schema,
        args.init_feishu_fields,
        args.test_feishu_write,
        args.test_webhook,
        args.list_feishu_chats,
        args.test_feishu_bot,
        args.local_only,
        args.local_structured_preview,
        args.local_html,
    ]
    if args.pilot_notice_ids_file and any(selected_without_pilot_file):
        parser.error("--pilot-notice-ids-file cannot be combined with other entrypoints")

    if args.local_only:
        try:
            results = run_once(enable_feishu=False, profile_id=args.profile)
        except ProfileNotFoundError as exc:
            print(str(exc))
            return 2
        _print_run_results(results)
        return _return_code_for_run(results, logger)

    if args.local_structured_preview:
        try:
            results = run_once(enable_feishu=False, structured_preview=True, profile_id=args.profile)
        except ProfileNotFoundError as exc:
            print(str(exc))
            return 2
        _print_run_results(results)
        print(f"preview_report: {structured_preview_report_path()}")
        return _return_code_for_run(results, logger)

    if args.local_html:
        try:
            run_kwargs = {
                "enable_feishu": False,
                "html_report": True,
                "profile_id": args.profile,
            }
            if args.ai_analysis or args.ai_analysis_limit is not None:
                run_kwargs["enable_ai_analysis"] = args.ai_analysis
                run_kwargs["ai_analysis_limit"] = args.ai_analysis_limit
            results = run_once(**run_kwargs)
        except ProfileNotFoundError as exc:
            print(str(exc))
            return 2
        _print_run_results(results)
        print(f"html_report: {html_report_path()}")
        return _return_code_for_run(results, logger)

    if args.init_feishu_schema or args.init_feishu_fields:
        client = FeishuClient(logger)
        try:
            result = client.init_schema()
        except FeishuConfigError as exc:
            print(str(exc))
            return 2
        except Exception as exc:
            print(f"Feishu schema init failed: {exc}")
            return 1
        print(f"target table_name: {result['table_name']}")
        print(f"existing field count: {result.get('existing_field_count', len(result['existing_fields']))}")
        print(f"created field count: {len(result['created_fields'])}")
        print(f"renamed fields: {', '.join(result['renamed_fields']) if result['renamed_fields'] else 'none'}")
        print(f"failed fields: {', '.join(result['failed_fields']) if result['failed_fields'] else 'none'}")
        return 0

    if args.test_feishu_write:
        client = FeishuClient(logger)
        _print_env_status(client)
        try:
            result = client.create_test_record()
        except FeishuConfigError as exc:
            print(str(exc))
            return 2
        except Exception as exc:
            print(f"Feishu test write failed: {exc}")
            return 1
        print("test record write succeeded")
        print(f"target table_id: {result['table_id']}")
        print(f"record_id: {result['record_id']}")
        return 0

    if args.test_webhook:
        client = FeishuClient(logger)
        _print_env_status(client)
        try:
            client.send_test_webhook()
        except FeishuConfigError as exc:
            print(str(exc))
            return 2
        except Exception as exc:
            print(f"Webhook test failed: {exc}")
            return 1
        print("Webhook test message sent")
        return 0

    if args.list_feishu_chats:
        client = FeishuClient(logger)
        try:
            chats = client.list_chats()
        except FeishuConfigError as exc:
            print(str(exc))
            return 2
        except Exception as exc:
            print(f"Feishu chat list failed: {exc}")
            return 1
        _print_feishu_chats(chats)
        return 0

    if args.test_feishu_bot:
        client = FeishuClient(logger)
        try:
            client.send_bot_message("TenderRadarLite 应用机器人发送测试成功")
        except FeishuConfigError as exc:
            print(str(exc))
            return 2
        except Exception as exc:
            print(f"Feishu bot test failed: {exc}")
            return 1
        print("bot test message sent")
        return 0

    if args.backfill_feishu:
        try:
            result = backfill_feishu(args.pilot_notice_ids_file)
        except FeishuConfigError as exc:
            print(str(exc))
            return 2
        except Exception as exc:
            print(f"Backfill failed: {exc}")
            return 1

        print(f"SQLite history total: {result.total_history_count}")
        print(f"Hit keyword history: {result.hit_history_count}")
        if not args.pilot_notice_ids_file and result.hit_history_count == 0:
            print("Local history exists but hit keyword count is 0")
            return 0
        print(f"Eligible for backfill: {result.eligible_count}")
        print(f"Feishu records written this run: {result.written_count}")
        print(f"Group bot summary sent: {'yes' if result.notified else 'no'}")
        print(f"Bot notices sent this run: {result.bot_sent_count}")
        return 0

    if args.reset_pilot_sync_state:
        if not args.pilot_notice_ids_file:
            parser.error("--reset-pilot-sync-state requires --pilot-notice-ids-file")
        result = reset_pilot_sync_state(args.pilot_notice_ids_file)
        print(f"Pilot notice ids targeted: {result.targeted_count}")
        print(f"Pilot sync rows reset: {result.reset_count}")
        return 0

    if args.pilot_notice_ids_file:
        try:
            result = run_pilot_notice_whitelist(args.pilot_notice_ids_file, execute=args.execute, profile_id=args.profile)
        except ProfileNotFoundError as exc:
            print(str(exc))
            return 2
        _print_pilot_notice_whitelist_result(result)
        return 0

    try:
        results = run_once(enable_feishu=True, profile_id=args.profile)
    except ProfileNotFoundError as exc:
        print(str(exc))
        return 2
    _print_run_results(results)
    return _return_code_for_run(results, logger)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
