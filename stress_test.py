import asyncio
import aiohttp
import time
import statistics

async def fetch(session, url, request_id):
    start_time = time.time()
    try:
        async with session.get(url, timeout=10) as response:
            status = response.status
            await response.text()  # Read body
            end_time = time.time()
            return {
                "id": request_id,
                "status": status,
                "latency": end_time - start_time,
                "success": 200 <= status < 300
            }
    except Exception as e:
        return {
            "id": request_id,
            "status": 0,
            "latency": time.time() - start_time,
            "success": False,
            "error": str(e)
        }

async def run_stress_test(url, count):
    print(f"\n--- Testing {count} concurrent requests to {url} ---")
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, url, i) for i in range(count)]
        start_test = time.time()
        results = await asyncio.gather(*tasks)
        end_test = time.time()

    successes = [r for r in results if r["success"]]
    latencies = [r["latency"] for r in results if r["success"]]
    
    total_time = end_test - start_test
    avg_latency = statistics.mean(latencies) if latencies else 0
    p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies) if latencies else 0
    
    print(f"Total time: {total_time:.2f}s")
    print(f"Successes: {len(successes)}/{count}")
    print(f"Failures: {count - len(successes)}/{count}")
    if successes:
        print(f"Avg Latency: {avg_latency:.4f}s")
        print(f"P95 Latency: {p95_latency:.4f}s")
    
    # Print first few failures if any
    failures = [r for r in results if not r["success"]]
    if failures:
        print("First few failure samples:")
        for f in failures[:3]:
            print(f"  ID {f['id']}: Status {f['status']} Error: {f.get('error', 'None')}")

async def main():
    api_url = "https://api-139601123738.us-central1.run.app/api/health"
    
    # Run tests sequentially
    await run_stress_test(api_url, 50)
    await run_stress_test(api_url, 100)
    await run_stress_test(api_url, 200)

if __name__ == "__main__":
    asyncio.run(main())
