"""Security: decoding, bit tricks, path normalisation, permissions. Answers are computed by the stdlib."""
from __future__ import annotations

import base64
import json
import posixpath
import random

from app.items import Family, Item, options_with

WORDS = ["admin", "token", "secret", "flag", "root", "guest", "login", "shell", "proxy", "cookie", "nonce",
         "salt", "hash", "cipher", "vault"]


def _b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def _rwx(octal: int) -> str:
    out = ""
    for shift in (6, 3, 0):
        bits = (octal >> shift) & 7
        out += ("r" if bits & 4 else "-") + ("w" if bits & 2 else "-") + ("x" if bits & 1 else "-")
    return out


def generate(rng: random.Random, level: int, spec: str) -> Item:
    if level == 1:
        stem_word = rng.choice(WORDS)
        suffix = str(rng.randint(1, 99))
        word = stem_word + suffix
        enc = _b64(word)
        same_len = [w for w in WORDS if len(w) == len(stem_word) and w != stem_word]
        wrong = [w + suffix for w in rng.sample(same_len, k=min(2, len(same_len)))]
        wrong += [stem_word + str(int(suffix) + 1), word[::-1], word.upper(), enc[::-1]]
        options, correct = options_with(rng, word, wrong)
        return Item(stem=f"Строка закодирована в Base64: {enc}\nЧто в ней?", options=options, correct=correct,
                    explanation="Base64 — кодирование, а не шифрование: оно обратимо без ключа.",
                    verify={"runner": "python", "code": f"import base64\nprint(base64.b64decode('{enc}').decode())",
                            "expect": word})
    if level == 2:
        a, b = rng.randint(16, 255), rng.randint(16, 255)
        ans = f"0x{a ^ b:02X}"
        options, correct = options_with(rng, ans, [f"0x{a | b:02X}", f"0x{a & b:02X}", f"0x{(a + b) & 0xFF:02X}"],
                                        lambda: f"0x{rng.randint(0, 255):02X}")
        return Item(stem=f"Чему равно 0x{a:02X} XOR 0x{b:02X}?", options=options, correct=correct,
                    explanation="XOR даёт 1 там, где биты различаются; повторный XOR тем же ключом "
                                "возвращает исходное.",
                    verify={"runner": "python", "code": f"print(f'0x{{{a} ^ {b}:02X}}')", "expect": ans})
    if level == 3:
        alg = rng.choice(["none", "HS256", "RS256", "ES256"])
        header = base64.urlsafe_b64encode(json.dumps({"alg": alg, "typ": "JWT"}, separators=(",", ":"))
                                          .encode()).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(json.dumps({"sub": str(rng.randint(100, 999)), "role": "user"},
                                                      separators=(",", ":")).encode()).decode().rstrip("=")
        token = f"{header}.{payload}." + ("" if alg == "none" else "c2lnbmF0dXJl")
        options, correct = options_with(rng, alg, [a for a in ["none", "HS256", "RS256", "ES256"] if a != alg])
        return Item(stem=f"Какой алгоритм подписи указан в заголовке JWT?\n{token}", options=options, correct=correct,
                    explanation="Заголовок — первая часть токена в base64url. alg=none означает отсутствие подписи: "
                                "сервер обязан такой токен отклонять.",
                    verify={"runner": "python", "code": (
                        "import base64, json\nh = '" + header + "'\nh += '=' * (-len(h) % 4)\n"
                        "print(json.loads(base64.urlsafe_b64decode(h))['alg'])"), "expect": alg})
    if level == 4:
        depth = rng.randint(2, 4)
        base = "/var/www/" + "/".join(rng.sample(["static", "img", "user", "files", "upload"], k=depth - 1))
        ups = rng.randint(depth, depth + 3)
        target = rng.choice(["etc/passwd", "etc/shadow", "root/.ssh/id_rsa", "proc/self/environ"])
        payload = "../" * ups + target
        ans = posixpath.normpath(posixpath.join(base, payload))
        wrong = [posixpath.join(base, target), posixpath.normpath(posixpath.join(base, "../" + target)),
                 "/var/" + target, "/var/www/" + target]
        options, correct = options_with(rng, ans, [w for w in wrong if w != ans],
                                        lambda: "/" + "/".join(rng.sample(["var", "www", "etc", "tmp", "srv"], k=2))
                                        + "/" + target)
        return Item(stem=f"Сервер склеивает путь: os.path.normpath('{base}/' + name), где name = '{payload}'.\n"
                         f"Какой файл он откроет?", options=options, correct=correct,
                    explanation="Лишние ../ упираются в корень; поэтому проверять нужно итоговый путь после "
                                "нормализации, а не входную строку.",
                    verify={"runner": "python",
                            "code": f"import posixpath\nprint(posixpath.normpath('{base}/' + '{payload}'))",
                            "expect": ans})
    umask = rng.choice([0o002, 0o022, 0o027, 0o077, 0o007, 0o037])
    is_dir = rng.random() < 0.5
    base_mode = 0o777 if is_dir else 0o666
    mode = base_mode & ~umask
    ans = _rwx(mode)
    wrong = [_rwx((0o666 if is_dir else 0o777) & ~umask), _rwx(base_mode - umask if base_mode - umask >= 0 else 0),
             _rwx(umask), _rwx(base_mode ^ 0o111)]
    options, correct = options_with(rng, ans, [w for w in wrong if w != ans],
                                    lambda: _rwx(rng.choice([0o640, 0o600, 0o750, 0o700, 0o644, 0o755, 0o664])))
    kind = "каталога (mkdir)" if is_dir else "файла (touch)"
    return Item(stem=f"umask {umask:04o}. Какие права получит новый {kind}?", options=options, correct=correct,
                explanation=f"Права = {base_mode:o} AND NOT umask. Для файлов база 666, для каталогов 777.",
                verify={"runner": "python", "code": f"print(oct({base_mode} & ~{umask}))", "expect_mode": mode})


FAMILY = Family(
    id="sec_decode", title="Безопасность: разбор данных и прав", topic="security", kind="code",
    specs=frozenset({"security", "devops"}), skills=("Web Security", "Linux"), generate=generate, a=1.3,
)
