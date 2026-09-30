# NewsWeaver/tests/test_evaluation.py

"""
고정 평가셋의 분할 배정이 결정적인지, 지표 계산이 정의대로인지 검증한다.
"""

from pathlib import Path

from news_weaver.selection.evaluation import (
    SPLIT_DEV,
    SPLIT_TEST,
    assign_splits,
    compute_metrics,
    filter_split,
    hash_bucket_split,
    read_eval_set,
    scale_k,
    write_eval_set,
)
from news_weaver.selection.interests import Topic

FIXTURE = Path(__file__).parent / "fixtures" / "selection_eval_small.jsonl"
TOPICS = (Topic("AI", ("AI",)),)


def make_hashes(count: int) -> list[str]:
    """분할 테스트용 해시 목록을 만든다."""
    return [f"article-{index}" for index in range(count)]


def test_split_is_deterministic() -> None:
    """같은 해시는 언제 실행해도 같은 분할이 된다."""
    for url_hash in make_hashes(50):
        assert hash_bucket_split(url_hash) == hash_bucket_split(url_hash)


def test_split_does_not_depend_on_input_order() -> None:
    """라벨 순서가 달라도 배정은 같다."""
    labels = {h: index % 4 == 0 for index, h in enumerate(make_hashes(40))}
    reversed_labels = dict(reversed(list(labels.items())))

    assert assign_splits(labels) == assign_splits(reversed_labels)


def test_existing_split_is_stable_when_labels_grow() -> None:
    """
    라벨이 늘어도 기존 기사의 분할은 바뀌지 않는다.

    분할이 흔들리면 test였던 기사가 dev로 넘어와 조정에 쓰일 수 있다.
    """
    hashes = make_hashes(60)
    small = assign_splits({h: index % 3 == 0 for index, h in enumerate(hashes[:30])})
    large = assign_splits({h: index % 3 == 0 for index, h in enumerate(hashes)})

    assert all(large[h] == small[h] for h in small)


def test_test_split_is_about_one_third() -> None:
    """test 비율이 약 1/3이다."""
    splits = assign_splits({h: False for h in make_hashes(600)})
    ratio = sum(split == SPLIT_TEST for split in splits.values()) / len(splits)

    assert 0.25 < ratio < 0.42


def test_both_splits_get_a_positive_when_possible() -> None:
    """
    관련 기사가 2건 이상이면 두 분할 모두 관련 기사를 갖는다.

    한쪽에 관련 기사가 없으면 그 분할의 재현율을 잴 수 없다.
    """
    hashes = make_hashes(200)
    # 해시 버킷상 모두 dev인 두 기사만 관련으로 둔다
    dev_only = [h for h in hashes if hash_bucket_split(h) == SPLIT_DEV][:2]
    labels = {h: h in dev_only for h in hashes}

    splits = assign_splits(labels)
    positive_splits = {splits[h] for h in dev_only}

    assert positive_splits == {SPLIT_DEV, SPLIT_TEST}


def test_eval_set_round_trip(tmp_path) -> None:
    """쓰고 다시 읽으면 같은 기사와 정답이 나온다."""
    records = read_eval_set(FIXTURE)
    path = tmp_path / "eval.jsonl"

    write_eval_set(path, records)

    assert read_eval_set(path) == records


def test_filter_split() -> None:
    """분할별로 걸러내고, all이면 전부 돌려준다."""
    records = read_eval_set(FIXTURE)

    assert len(filter_split(records, SPLIT_TEST)) == 5
    assert len(filter_split(records, SPLIT_DEV)) == 1
    assert len(filter_split(records, "all")) == 6


def test_scale_k_keeps_reference_ratio() -> None:
    """기준 60건에서는 K가 그대로이고, 건수가 줄면 비례해 준다."""
    assert scale_k(10, 60) == 10
    assert scale_k(10, 20) == 3
    assert scale_k(10, 1) == 1


def test_metrics_on_fixture() -> None:
    """
    작은 평가셋에서 정밀도와 재현율을 손으로 계산한 값과 비교한다.

    6건이면 P@1, R@3이다. 제목과 요약 모두 걸린 a가 1위(관련)이므로 정밀도 1.0,
    주제에 걸린 a·b·c 중 관련은 a·c이고 e는 놓치므로 재현율 2/3이다.
    """
    metrics = compute_metrics(read_eval_set(FIXTURE), TOPICS)

    assert (metrics.total, metrics.relevant) == (6, 3)
    assert (metrics.precision_k, metrics.recall_k) == (1, 3)
    assert metrics.precision == 1.0
    assert metrics.recall == 2 / 3
