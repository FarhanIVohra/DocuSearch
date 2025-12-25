import os
import argparse
import time
from typing import List

from .index.indexer import build_index
from .service.search_service import SearchService


def load_index_default(docs_dir: str):
    if not os.path.isdir(docs_dir):
        raise SystemExit(f"Documents directory not found: {docs_dir}")
    return build_index(docs_dir)


def run_interactive(service: SearchService):
    print("Interactive search. Type 'exit' to quit.")
    while True:
        try:
            q = input("query> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if q.lower() in {"exit", ":q", "quit"}:
            break
        result = service.search(q)
        print(f"cached={result['cached']} elapsed_ms={result['elapsed_ms']:.3f}")
        for doc_id, score in result["results"][:10]:
            print(f"  doc_id={doc_id} score={score:.4f}")


def run_benchmark(service: SearchService, queries: List[str], repeat: int = 2):
    for _ in range(3):
        for q in queries:
            service.search(q)

    service_no_cache = SearchService(service.index, cache_capacity=0)

    def run(name: str, svc: SearchService) -> float:
        start = time.perf_counter()
        for _ in range(repeat):
            for q in queries:
                svc.search(q)
        return (time.perf_counter() - start) * 1000

    t_nocache = run("no_cache", service_no_cache)
    t_cache = run("cache", service)

    print("Benchmark results:")
    print(f"  no_cache_time_ms={t_nocache:.2f}")
    print(f"  cache_time_ms={t_cache:.2f}")
    print("Service stats with cache:")
    print(service.stats())


def main():
    parser = argparse.ArgumentParser(description="Hackathon Search Engine CLI")
    parser.add_argument("--docs", default=os.path.join(os.path.dirname(__file__), "data", "documents"), help="Documents directory")
    parser.add_argument("--cache-capacity", type=int, default=256, help="LRU cache capacity (0 to disable)")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("repl", help="Interactive search prompt")

    bench = sub.add_parser("bench", help="Benchmark repeated queries to show cache effectiveness")
    bench.add_argument("--repeat", type=int, default=3, help="Repetitions of the query set")

    args = parser.parse_args()

    index = load_index_default(args.docs)
    service = SearchService(index, cache_capacity=args.cache_capacity)

    if args.cmd == "bench":
        queries = [
            "search engines",
            "index documents",
            "working completely",
            "search engines",
            "how it works",
            "search indexing",
            "search engines",
        ]
        run_benchmark(service, queries, repeat=args.repeat)
    else:
        run_interactive(service)


if __name__ == "__main__":
    main()
