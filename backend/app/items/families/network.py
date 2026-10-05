"""Networks: IPv4 subnetting. Answers come from the ipaddress module."""
from __future__ import annotations

import ipaddress
import random

from app.items import Family, Item, near_int, options_with


def _ip(rng: random.Random) -> str:
    first = rng.choice([10, 172, 192])
    second = {10: rng.randint(0, 255), 172: rng.randint(16, 31), 192: 168}[first]
    return f"{first}.{second}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"


def _ip_filler(rng: random.Random, around: str):
    base = int(ipaddress.ip_address(around))
    return lambda: str(ipaddress.ip_address((base + rng.choice([-1, 1]) * rng.choice([1, 64, 128, 256, 512])) % 2**32))


def generate(rng: random.Random, level: int, spec: str) -> Item:
    ip = _ip(rng)
    if level == 1:
        p = rng.randint(24, 29)
        hosts = 2 ** (32 - p) - 2
        options, correct = options_with(rng, hosts, [2 ** (32 - p), 2 ** (32 - p) - 1, 2 ** (32 - p - 1)],
                                        near_int(rng, hosts, 6))
        return Item(stem=f"Сколько адресов для узлов в подсети /{p}?", options=options, correct=correct,
                    explanation="2^(32 − префикс) адресов минус адрес сети и широковещательный.",
                    verify={"runner": "ipaddress", "expr": f"len(list(ipaddress.ip_network('10.0.0.0/{p}').hosts()))",
                            "expect": str(hosts)})
    p = rng.choice([20, 21, 22, 23, 26, 27, 28]) if level >= 3 else rng.choice([24, 25, 26, 27])
    net = ipaddress.ip_network(f"{ip}/{p}", strict=False)
    if level == 2:
        ans = str(net.network_address)
        wrong = [str(ipaddress.ip_network(f"{ip}/24", strict=False).network_address), ip,
                 str(net.network_address + 1), str(net.broadcast_address)]
        stem, why = f"Адрес сети для {ip}/{p}?", "Адрес сети — IP AND маска."
        expr = f"str(ipaddress.ip_network('{ip}/{p}', strict=False).network_address)"
    elif level == 3:
        ans = str(net.broadcast_address)
        wrong = [str(net.network_address), str(net.broadcast_address - 1),
                 str(ipaddress.ip_network(f"{ip}/24", strict=False).broadcast_address)]
        stem, why = f"Широковещательный адрес для {ip}/{p}?", "Все биты узла равны единице."
        expr = f"str(ipaddress.ip_network('{ip}/{p}', strict=False).broadcast_address)"
    elif level == 4:
        inside = str(net.network_address + rng.randint(1, net.num_addresses - 2))
        outs = [str(net.broadcast_address + rng.randint(1, 300)), str(net.network_address - rng.randint(1, 300)),
                str(net.broadcast_address + net.num_addresses // 2 + 1)]
        far = _ip_filler(rng, str(net.broadcast_address))

        def outside() -> str:
            while True:
                candidate = far()
                if ipaddress.ip_address(candidate) not in net:
                    return candidate
        options, correct = options_with(rng, inside, [o for o in outs if ipaddress.ip_address(o) not in net], outside)
        return Item(stem=f"Какой адрес находится в той же подсети, что и {ip}/{p}?", options=options, correct=correct,
                    explanation=f"Подсеть {net} охватывает {net.network_address} — {net.broadcast_address}.",
                    verify={"runner": "ipaddress", "expr": f"str(ipaddress.ip_address('{inside}') in "
                            f"ipaddress.ip_network('{net}'))", "expect": "True", "predicate": True})
    else:
        other = str(net.network_address + rng.randint(net.num_addresses, net.num_addresses * 6))
        a, b = int(ipaddress.ip_address(ip)), int(ipaddress.ip_address(other))
        prefix = 32 - (a ^ b).bit_length()
        ans = str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))
        wrong = [str(ipaddress.ip_network(f"{ip}/{prefix + 1}", strict=False)),
                 str(ipaddress.ip_network(f"{ip}/{max(8, prefix - 1)}", strict=False)),
                 str(ipaddress.ip_network(f"{ip}/{p}", strict=False))]
        stem = f"Наименьшая сеть, в которую попадают и {ip}, и {other}?"
        why = "Нужен самый длинный общий префикс двух адресов: XOR покажет первый различающийся бит."
        expr = (f"str(ipaddress.ip_network('{ip}/' + str(32 - (int(ipaddress.ip_address('{ip}')) ^ "
                f"int(ipaddress.ip_address('{other}'))).bit_length()), strict=False))")
    if level == 5:
        def filler() -> str:
            return str(ipaddress.ip_network(f"{ip}/{rng.choice(range(max(8, prefix - 4), min(30, prefix + 5)))}",
                                            strict=False))
    else:
        filler = _ip_filler(rng, ans)
    options, correct = options_with(rng, ans, [w for w in wrong if w != ans], filler)
    return Item(stem=stem, options=options, correct=correct, explanation=why,
                verify={"runner": "ipaddress", "expr": expr, "expect": ans})


FAMILY = Family(
    id="net_ipv4", title="Сети: адресация IPv4", topic="network", kind="code",
    specs=frozenset({"devops", "security", "embedded", "backend"}), skills=("Networking",), generate=generate, a=1.3,
)
