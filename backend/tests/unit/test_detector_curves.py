from app.validation import detector_curves as dc


def test_curves_are_monotone_and_mark_product_threshold():
    out = dc.curves(n=150, seed=3, leak_share=0.5)
    assert set(out) == set(dc.SIGNALS)
    for name, rows in out.items():
        for _, caught, false in rows:
            assert 0.0 <= caught <= 1.0 and 0.0 <= false <= 1.0
        thresholds, product, _ = dc.SIGNALS[name]
        assert product in thresholds
        # Stricter thresholds flag no more sessions (≥ grows, < shrinks along the listed order).
        falses = [r[2] for r in rows]
        assert falses == sorted(falses, reverse=True)


def test_leak_is_caught_more_often_than_honest_at_product_point():
    out = dc.curves(n=300, seed=5, leak_share=0.5)
    name = "Быстрые маловероятные верные ответы"
    thresholds, product, _ = dc.SIGNALS[name]
    _, caught, false = out[name][thresholds.index(product)]
    assert caught > false


def test_markdown_has_star():
    text = dc.markdown({7: dc.curves(50, 7, 0.5)}, [7], 50, 0.5)
    assert "★" in text and "поймано / ложно" in text
