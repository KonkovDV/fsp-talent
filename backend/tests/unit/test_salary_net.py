from app.services.salary_net import annual_tax, gross_for_net, net_monthly


def test_scale_edges():
    assert annual_tax(2_400_000) == 312_000
    assert annual_tax(2_400_000 + 100) == 312_000 + 15
    assert net_monthly(200_000) == 174_000
    # 300 000 a month crosses into the 15% band.
    assert net_monthly(300_000) == 259_000


def test_round_trip_stays_within_a_hundred():
    for net in (100_000, 174_000, 250_000, 400_000):
        back = net_monthly(gross_for_net(net))
        assert 0 <= back - net <= 100


def test_zero_and_order():
    assert net_monthly(0) == 0 and gross_for_net(0) == 0
    assert net_monthly(150_000) < net_monthly(250_000) < 250_000
