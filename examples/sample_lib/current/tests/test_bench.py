from samplelib.perf import checksum


def test_checksum_benchmark(benchmark):
    data = list(range(20000))
    benchmark(checksum, data)
