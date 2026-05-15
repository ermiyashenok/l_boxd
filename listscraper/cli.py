import argparse
from datetime import datetime
from listscraper.instance_class import ScraperInstance
from listscraper.checkimport_functions import import_urls_from_file
from listscraper.utility_functions import concat_films, save_to_csv, save_to_json

def parse_page_range(parser: argparse.ArgumentParser, page_str: str) -> tuple[int, int] | None:
    if not page_str:
        return None
    try:
        parts = page_str.split("-")
        if len(parts) == 1:
            n = int(parts[0])
            if n < 1:
                raise ValueError
            return (n, n)
        elif len(parts) == 2:
            start = int(parts[0])
            end = int(parts[1])
            if start < 1 or end < 1 or start > end:
                raise ValueError
            return (start, end)
        else:
            raise ValueError
    except ValueError:
        parser.error("--pages must be a single number (e.g. '3') or a range (e.g. '1-5')")

def main():
    print("=============================================")
    print(" Letterboxd List Scraper")
    print(" github.com/your-username/Letterboxd-list-scraper")
    print("=============================================\n")

    parser = argparse.ArgumentParser(
        prog="listscraper",
        description="Scrape Letterboxd lists into CSV or JSON files",
        epilog="Examples:\n"
               "  python -m listscraper https://letterboxd.com/dave/list/official-top-250-narrative-feature-films/\n"
               "  python -m listscraper -f my_lists.txt --concat -ofe json\n"
               "  python -m listscraper https://letterboxd.com/joelhaver/watchlist/ -p 1-3 -on joel_watchlist",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("list_url", nargs="*", default=[], help="One or more Letterboxd URLs, space-separated")
    parser.add_argument("-f", "--file", type=str, default=None, help="Path to a .txt file containing one URL per line")
    parser.add_argument("-p", "--pages", type=str, default=None, help="Page range as 'N' (single page) or 'N-M' (range). E.g. '2' or '1-5'")
    parser.add_argument("-on", "--output-name", type=str, default=None, help="Custom output filename (without extension). If multiple URLs given, appends _1, _2 etc.")
    parser.add_argument("-op", "--output-path", type=str, default="scraper_outputs/", help="Directory to write output files")
    parser.add_argument("-ofe", "--output-file-extension", type=str, default="csv", help="Output format: csv or json")
    parser.add_argument("--concat", action="store_true", help="Merge all scraped lists into a single output file")
    parser.add_argument("-t", "--threads", type=int, default=4, help="Max number of concurrent scraping threads")

    args = parser.parse_args()

    urls = list(args.list_url)
    if args.file:
        try:
            urls.extend(import_urls_from_file(args.file))
        except (FileNotFoundError, ValueError) as e:
            parser.error(str(e))

    if not urls:
        parser.error("No URLs provided. Pass a URL directly or use --file.")

    page_range = parse_page_range(parser, args.pages)

    if args.output_file_extension not in ("csv", "json"):
        parser.error("Output extension must be 'csv' or 'json'.")

    print(f"Found {len(urls)} list(s) to scrape\n")

    all_films_lists = []
    successful_lists = 0

    for i, url in enumerate(urls):
        out_name = args.output_name
        if out_name and len(urls) > 1:
            out_name = f"{out_name}_{i+1}"
            
        try:
            scraper = ScraperInstance(
                list_url=url,
                output_name=out_name,
                output_path=args.output_path,
                output_format=args.output_file_extension,
                page_range=page_range,
                thread_count=args.threads
            )
            
            films = scraper.run(save=not args.concat)
            if films:
                all_films_lists.append(films)
                successful_lists += 1
                
        except Exception as e:
            if isinstance(e, (ValueError, FileNotFoundError, OSError)):
                parser.error(str(e))
            print(f"Warning: Failed to process {url} - {e}. Skipping to next...")
            continue

    if args.concat and all_films_lists:
        merged = concat_films(all_films_lists)
        out_name = args.output_name if args.output_name else f"concat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if args.output_file_extension == "csv":
            save_to_csv(merged, args.output_path, out_name)
        else:
            save_to_json(merged, args.output_path, out_name)
            
        print(f"Concatenated {len(all_films_lists)} lists into {len(merged)} unique films -> saved to {args.output_path}")
        
    print("\n=============================================")
    print(f" Done. {successful_lists} list(s) scraped successfully.")
    print(f" Output written to: {args.output_path}")
    print("=============================================")
