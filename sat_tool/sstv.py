"""v1.9.0: SSTV — codificação e decodificação (somente numpy).

Modos: Robot 36/72, Martin M1/M2, Scottie S1/S2/DX e PD 50/90/120/160/180/240/290 (os da ISS e dos
satélites russos). A decodificação é em fluxo: o áudio chega em blocos (RTL-SDR ou placa de som do
rádio), o cabeçalho VIS identifica o modo, e cada linha é posicionada pelo pulso de sincronismo, com
ajuste contínuo de inclinação (diferença de relógio entre transmissor e placa de som). O desvio de tom
(rádio fora de sintonia, Doppler residual em SSB) é medido no tom de 1900 Hz do cabeçalho e descontado.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

SYNC_HZ, BLACK_HZ, WHITE_HZ, LEADER_HZ = 1200.0, 1500.0, 2300.0, 1900.0


@dataclass(frozen=True)
class Mode:
    name: str
    vis: int
    width: int
    height: int
    segments: tuple            # (canal, duração ms): canal = frequência fixa (float) ou nome do componente
    color: str                 # "GBR" (RGB), "YUV420" (Robot 36), "YUV422" (Robot 72), "PD"
    first_sync_ms: float = 0.0  # Scottie: pulso inicial antes da primeira linha
    rows_per_line: int = 1      # PD: cada varredura leva duas linhas da imagem

    @property
    def line_ms(self) -> float:
        return sum(d for _, d in self.segments)

    @property
    def lines(self) -> int:
        return self.height // self.rows_per_line

    @property
    def sync_offset_ms(self) -> float:
        """Posição do pulso de sincronismo (1200 Hz, o mais longo) dentro da linha."""
        best, pos, at = 0.0, 0.0, 0.0
        for ch, d in self.segments:
            if ch == SYNC_HZ and d > best:
                best, at = d, pos
            pos += d
        return at

    @property
    def sync_ms(self) -> float:
        return max(d for ch, d in self.segments if ch == SYNC_HZ)

    @property
    def duration_s(self) -> float:
        return (self.first_sync_ms + self.lines * self.line_ms) / 1000.0


def _martin(name, vis, scan):
    return Mode(name, vis, 320, 256, ((SYNC_HZ, 4.862), (BLACK_HZ, 0.572), ("G", scan), (BLACK_HZ, 0.572),
                                       ("B", scan), (BLACK_HZ, 0.572), ("R", scan), (BLACK_HZ, 0.572)), "GBR")


def _scottie(name, vis, scan):
    return Mode(name, vis, 320, 256, ((BLACK_HZ, 1.5), ("G", scan), (BLACK_HZ, 1.5), ("B", scan),
                                       (SYNC_HZ, 9.0), (BLACK_HZ, 1.5), ("R", scan)), "GBR", first_sync_ms=9.0)


def _pd(name, vis, width, height, pixel_ms):
    scan = pixel_ms * width
    return Mode(name, vis, width, height, ((SYNC_HZ, 20.0), (BLACK_HZ, 2.08), ("Y0", scan), ("RY", scan),
                                           ("BY", scan), ("Y1", scan)), "PD", rows_per_line=2)


MODES = {m.name: m for m in (
    Mode("Robot 36", 8, 320, 240, ((SYNC_HZ, 9.0), (BLACK_HZ, 3.0), ("Y", 88.0), ("SEP", 4.5),
                                   (LEADER_HZ, 1.5), ("C", 44.0)), "YUV420"),
    Mode("Robot 72", 12, 320, 240, ((SYNC_HZ, 9.0), (BLACK_HZ, 3.0), ("Y", 138.0), (BLACK_HZ, 4.5),
                                    (LEADER_HZ, 1.5), ("RY", 69.0), (WHITE_HZ, 4.5), (LEADER_HZ, 1.5),
                                    ("BY", 69.0)), "YUV422"),
    _martin("Martin M1", 44, 146.432), _martin("Martin M2", 40, 73.216),
    _scottie("Scottie S1", 60, 138.240), _scottie("Scottie S2", 56, 88.064), _scottie("Scottie DX", 76, 345.6),
    _pd("PD 50", 93, 320, 256, 0.286), _pd("PD 90", 99, 320, 256, 0.532), _pd("PD 120", 95, 640, 496, 0.190),
    _pd("PD 160", 98, 512, 400, 0.382), _pd("PD 180", 96, 640, 496, 0.286), _pd("PD 240", 97, 640, 496, 0.382),
    _pd("PD 290", 94, 800, 616, 0.286),
)}
BY_VIS = {m.vis: m for m in MODES.values()}


# ------------------------------------------------------------------ cor
def rgb_to_ycc(rgb):
    r, g, b = (rgb[..., i].astype(np.float64) for i in range(3))
    y = 16.0 + (65.738 * r + 129.057 * g + 25.064 * b) / 256.0
    cr = 128.0 + (112.439 * r - 94.154 * g - 18.285 * b) / 256.0
    cb = 128.0 + (-37.945 * r - 74.494 * g + 112.439 * b) / 256.0
    return y, cr, cb


def ycc_to_rgb(y, cr, cb):
    y, cr, cb = (np.asarray(v, dtype=np.float64) for v in (y, cr, cb))
    r = (298.082 * (y - 16) + 408.583 * (cr - 128)) / 256.0
    g = (298.082 * (y - 16) - 100.291 * (cb - 128) - 208.120 * (cr - 128)) / 256.0
    b = (298.082 * (y - 16) + 516.411 * (cb - 128)) / 256.0
    return np.clip(np.stack([r, g, b], axis=-1), 0, 255).astype(np.uint8)


def value_to_hz(v):
    return BLACK_HZ + np.asarray(v, dtype=np.float64) * (WHITE_HZ - BLACK_HZ) / 255.0


def hz_to_value(f):
    return np.clip((np.asarray(f, dtype=np.float64) - BLACK_HZ) * 255.0 / (WHITE_HZ - BLACK_HZ), 0, 255)


# ------------------------------------------------------------- codificação
def fit_image(rgb: np.ndarray, mode: Mode) -> np.ndarray:
    """Redimensiona (vizinho mais próximo, sem dependências) para o tamanho do modo."""
    rgb = np.asarray(rgb)
    if rgb.ndim == 2:
        rgb = np.stack([rgb] * 3, axis=-1)
    rgb = rgb[..., :3]
    h, w = rgb.shape[:2]
    ys = (np.arange(mode.height) * h / mode.height).astype(int)
    xs = (np.arange(mode.width) * w / mode.width).astype(int)
    return rgb[ys][:, xs].astype(np.uint8)


class _Tone:
    def __init__(self, rate):
        self.rate, self.phase, self.out, self.t, self.n = float(rate), 0.0, [], 0.0, 0

    def add(self, freqs, duration_ms):
        """Frequência fixa ou vetor de frequências espalhado por duration_ms (fase contínua)."""
        self.t += duration_ms / 1000.0
        target = int(round(self.t * self.rate))
        count = target - self.n
        if count <= 0:
            return
        self.n = target
        freqs = np.atleast_1d(np.asarray(freqs, dtype=np.float64))
        if len(freqs) == 1:
            inst = np.full(count, freqs[0])
        else:
            idx = np.minimum((np.arange(count) * len(freqs) / count).astype(int), len(freqs) - 1)
            inst = freqs[idx]
        ph = self.phase + np.cumsum(2 * np.pi * inst / self.rate)
        self.phase = float(ph[-1] % (2 * np.pi))
        self.out.append(np.sin(ph).astype(np.float32))

    def audio(self):
        return np.concatenate(self.out) if self.out else np.zeros(0, np.float32)


def vis_header(tone: _Tone, vis: int):
    tone.add(LEADER_HZ, 300); tone.add(SYNC_HZ, 10); tone.add(LEADER_HZ, 300); tone.add(SYNC_HZ, 30)
    bits = [(vis >> i) & 1 for i in range(7)]
    bits.append(sum(bits) % 2)  # paridade par
    for bit in bits:
        tone.add(1100.0 if bit else 1300.0, 30)
    tone.add(SYNC_HZ, 30)


def encode(rgb: np.ndarray, mode_name: str = "Robot 36", rate: int = 48000, amplitude: float = 0.8) -> np.ndarray:
    """Imagem RGB (H×W×3) → áudio SSTV (float32, -1..1), com cabeçalho VIS."""
    mode = MODES[mode_name]
    img = fit_image(rgb, mode)
    tone = _Tone(rate)
    vis_header(tone, mode.vis)
    if mode.first_sync_ms:
        tone.add(SYNC_HZ, mode.first_sync_ms)
    y, cr, cb = rgb_to_ycc(img) if mode.color != "GBR" else (None, None, None)
    for line in range(mode.lines):
        row = line * mode.rows_per_line
        for ch, d in mode.segments:
            if isinstance(ch, float):
                tone.add(ch, d)
                continue
            if ch in "RGB":
                tone.add(value_to_hz(img[row, :, "RGB".index(ch)]), d)
            elif ch == "Y":
                tone.add(value_to_hz(y[row]), d)
            elif ch == "Y0":
                tone.add(value_to_hz(y[row]), d)
            elif ch == "Y1":
                tone.add(value_to_hz(y[min(row + 1, mode.height - 1)]), d)
            elif ch in ("RY", "BY"):
                plane = cr if ch == "RY" else cb
                rows = plane[row:row + mode.rows_per_line]
                tone.add(value_to_hz(rows.mean(axis=0)), d)
            elif ch == "SEP":   # Robot 36: 1500 Hz antes de R-Y (linha par), 2300 Hz antes de B-Y (ímpar)
                tone.add(BLACK_HZ if line % 2 == 0 else WHITE_HZ, d)
            elif ch == "C":     # Robot 36: crominância alternada, média do par de linhas
                plane = cr if line % 2 == 0 else cb
                pair = plane[line - line % 2:line - line % 2 + 2]
                tone.add(value_to_hz(pair.mean(axis=0)), d)
    return (tone.audio() * float(amplitude)).astype(np.float32)


def write_wav(path, audio: np.ndarray, rate: int = 48000):
    import wave
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(int(rate)); wav.writeframes(pcm)


def read_wav(path):
    import wave
    with wave.open(str(path), "rb") as wav:
        rate, channels, width = wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
        raw = wav.readframes(wav.getnframes())
    if width == 2:
        data = np.frombuffer(raw, "<i2").astype(np.float32) / 32768.0
    elif width == 1:
        data = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128.0
    else:
        data = np.frombuffer(raw, "<i4").astype(np.float32) / 2147483648.0
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data, rate


# ----------------------------------------------------------- decodificação
def _lowpass(cutoff, rate, taps=63):
    n = np.arange(taps) - (taps - 1) / 2
    h = np.sinc(2 * cutoff / rate * n) * np.blackman(taps)
    return (h / h.sum()).astype(np.float64)


@dataclass
class Image:
    mode: Mode
    pixels: np.ndarray
    rows_done: int = 0
    offset_hz: float = 0.0
    slant_ppm: float = 0.0
    meta: dict = field(default_factory=dict)


class Decoder:
    """Decodificador em fluxo. feed(áudio) devolve eventos:

    ("start", Image) quando o VIS é reconhecido; ("rows", Image, primeira, última) a cada linha;
    ("done", Image) ao terminar. O mesmo objeto de Image é atualizado no lugar.
    """

    MAX_BUFFER_S = 30.0

    def __init__(self, rate: int = 48000):
        self.rate = int(rate)
        self.dec = max(1, int(round(self.rate / 24000)))
        self.fr = self.rate / self.dec                    # taxa da série de frequência
        self.taps = _lowpass(1600.0, self.rate, taps=int(self.rate // 160) | 1)   # corta a imagem em -(f+1900) Hz
        self.reset()

    # ---- estado
    def reset(self):
        self._hist = np.zeros(len(self.taps) - 1, complex)
        self._phase = 0.0
        self._prev = None
        self._dphase = 0
        self.freq = np.zeros(0)          # frequência instantânea (Hz), índice absoluto a partir de self.base
        self.base = 0
        self.image: Image | None = None
        self._line = 0
        self._t0 = 0.0
        self._fit: list = []
        self._scan_from = 0
        self.cancel_image()

    def cancel_image(self):
        self.image = None
        self._line = 0
        self._fit = []

    def force_mode(self, name: str, start_s: float = 0.0):
        """Começa uma imagem sem VIS (modo escolhido pelo operador), a partir de start_s do fluxo."""
        self._begin(MODES[name], int(start_s * self.fr), 0.0)

    # ---- sinal → frequência
    def _demod(self, audio):
        x = np.asarray(audio, dtype=np.float64)
        n = np.arange(len(x))
        step = 2 * np.pi * LEADER_HZ / self.rate
        mixed = x * np.exp(-1j * (self._phase + step * n))
        self._phase = float((self._phase + step * len(x)) % (2 * np.pi))
        data = np.concatenate([self._hist, mixed])
        full = np.convolve(data, self.taps, mode="valid")
        self._hist = data[-(len(self.taps) - 1):]
        y = full[self._dphase::self.dec]
        self._dphase = (self._dphase - len(full)) % self.dec
        if not len(y):
            return np.zeros(0)
        first = y[0] if self._prev is None else self._prev
        prev = np.concatenate([[first], y[:-1]])
        self._prev = y[-1]
        d = np.angle(y * np.conj(prev))
        return LEADER_HZ + d * self.fr / (2 * np.pi)

    def feed(self, audio) -> list:
        f = self._demod(audio)
        if len(f):
            self.freq = np.concatenate([self.freq, f])
        events = []
        while True:
            before = len(events)
            if self.image is None:
                self._find_vis(events)
            else:
                self._decode_lines(events)
            if len(events) == before:
                break
        self._trim()
        return events

    def _trim(self):
        keep = int(self.MAX_BUFFER_S * self.fr)
        if self.image is not None:
            # mantém desde a linha anterior (ajuste de sincronismo)
            need = int(self._line_start(max(0, self._line - 1))) - self.base - int(self.fr * 0.05)
            drop = max(0, min(need, len(self.freq)))
        else:
            drop = max(0, min(self._scan_from - self.base - int(self.fr), len(self.freq) - keep))
            drop = max(drop, len(self.freq) - keep)
        if drop > 0:
            self.freq = self.freq[drop:]
            self.base += drop

    # ---- VIS
    def _mean(self, start, ms):
        a = int(round(start)) - self.base
        b = a + max(1, int(round(ms * self.fr / 1000)))
        if a < 0 or b > len(self.freq):
            return None
        return float(np.median(self.freq[a:b]))

    def _find_vis(self, events):
        fr = self.fr
        end = self.base + len(self.freq) - int(0.33 * fr)    # precisa de 300 ms depois do bit de partida
        start = max(self._scan_from, self.base + int(0.31 * fr))
        if end <= start:
            return
        seg = self.freq[start - self.base:end - self.base]
        # transições 1900 → 1200: candidatos a bit de partida
        low = seg < 1550
        edges = np.flatnonzero(low[1:] & ~low[:-1]) + 1 + start
        for edge in edges:
            leader = self._mean(edge - 0.2 * fr, 190)
            if leader is None or abs(leader - LEADER_HZ) > 150:
                continue
            offset = leader - LEADER_HZ
            startbit = self._mean(edge + 0.005 * fr, 20)
            if startbit is None or abs(startbit - offset - SYNC_HZ) > 80:
                continue
            bits = []
            for k in range(8):
                v = self._mean(edge + (0.030 + 0.030 * k + 0.005) * fr, 20)
                if v is None:
                    return   # ainda sem dados: tenta no próximo bloco a partir daqui
                v -= offset
                if not 1030 <= v <= 1370:
                    bits = None
                    break
                bits.append(1 if v < 1200 else 0)
            if not bits or sum(bits) % 2:
                continue
            vis = sum(b << i for i, b in enumerate(bits[:7]))
            mode = BY_VIS.get(vis)
            if mode is None:
                continue
            self._begin(mode, edge + 0.300 * fr, offset)
            events.append(("start", self.image))
            return
        self._scan_from = max(self._scan_from, end - int(0.02 * fr))

    def _begin(self, mode, t0, offset):
        self.image = Image(mode, np.zeros((mode.height, mode.width, 3), np.uint8), offset_hz=offset)
        self._t0 = float(t0) + mode.first_sync_ms * self.fr / 1000.0
        self._line = 0
        self._fit = []
        self._chroma = None

    # ---- linhas
    def _samples(self, ms):
        return ms * self.fr / 1000.0

    def _line_start(self, n):
        """Início previsto da linha n pelo ajuste linear dos pulsos de sincronismo medidos."""
        mode = self.image.mode
        nominal = self._samples(mode.line_ms)
        if len(self._fit) >= 6:
            xs = np.array([p[0] for p in self._fit[-80:]], float)
            ys = np.array([p[1] for p in self._fit[-80:]], float)
            slope, icpt = np.polyfit(xs, ys, 1)
            if abs(slope / nominal - 1) < 0.01:
                return icpt + slope * n
        if self._fit:
            k, pos = self._fit[-1]
            return pos + (n - k) * nominal
        return self._t0 + n * nominal

    def _measure_sync(self, n, predicted):
        mode = self.image.mode
        width = int(self._samples(mode.sync_ms))
        center = predicted + self._samples(mode.sync_offset_ms)
        span = int(self._samples(max(1.5, mode.sync_ms * 0.4)))
        a = int(center) - span - self.base
        b = int(center) + span + width - self.base
        if a < 0 or b > len(self.freq):
            return None
        win = np.abs(self.freq[a:b] - self.image.offset_hz - SYNC_HZ) < 150
        score = np.convolve(win.astype(float), np.ones(width), "valid") / width
        k = int(np.argmax(score))
        if score[k] < 0.6:
            return None
        return a + self.base + k - self._samples(mode.sync_offset_ms)

    def _component(self, start, ms, count):
        """Média da frequência em cada pixel (cumsum com interpolação fracionária)."""
        a0 = max(0, int(np.floor(start - self.base)))
        part = self.freq[a0:a0 + int(np.ceil(self._samples(ms))) + 3] - self.image.offset_hz
        edges = np.clip(start - self.base - a0 + np.arange(count + 1) * self._samples(ms) / count, 0, len(part))
        c = np.concatenate([[0.0], np.cumsum(part)])
        ci = np.interp(edges, np.arange(len(c)), c)
        width = np.maximum(np.diff(edges), 1e-9)
        return hz_to_value(np.diff(ci) / width)

    def _decode_lines(self, events):
        mode = self.image.mode
        while self._line < mode.lines:
            n = self._line
            predicted = self._line_start(n)
            end = predicted + self._samples(mode.line_ms * 1.02) + self._samples(mode.sync_ms * 2)
            if end - self.base > len(self.freq):
                return
            measured = self._measure_sync(n, predicted)
            if measured is not None and abs(measured - predicted) < self._samples(max(2.0, mode.sync_ms * 0.4)):
                self._fit.append((n, measured))
            start = self._line_start(n) if len(self._fit) >= 6 else (measured if measured is not None else predicted)
            self._render(n, start)
            first = n * mode.rows_per_line
            self.image.rows_done = min(mode.height, first + mode.rows_per_line)
            events.append(("rows", self.image, first, self.image.rows_done - 1))
            self._line += 1
        if len(self._fit) >= 6:
            xs = np.array([p[0] for p in self._fit], float); ys = np.array([p[1] for p in self._fit], float)
            slope = np.polyfit(xs, ys, 1)[0]
            self.image.slant_ppm = (slope / self._samples(mode.line_ms) - 1) * 1e6
        img = self.image
        events.append(("done", img))
        self._scan_from = int(self._line_start(mode.lines))
        self.cancel_image()

    def _render(self, n, start):
        mode, img = self.image.mode, self.image
        pos, parts = start, {}
        for ch, d in mode.segments:
            if not isinstance(ch, float) and ch != "SEP":
                parts[ch] = self._component(pos, d, mode.width)
            pos += self._samples(d)
        row = n * mode.rows_per_line
        if mode.color == "GBR":
            img.pixels[row] = np.stack([parts["R"], parts["G"], parts["B"]], axis=-1).astype(np.uint8)
        elif mode.color == "PD":
            img.pixels[row] = ycc_to_rgb(parts["Y0"], parts["RY"], parts["BY"])
            if row + 1 < mode.height:
                img.pixels[row + 1] = ycc_to_rgb(parts["Y1"], parts["RY"], parts["BY"])
        elif mode.color == "YUV422":
            img.pixels[row] = ycc_to_rgb(parts["Y"], parts["RY"], parts["BY"])
        else:   # Robot 36: R-Y nas linhas pares, B-Y nas ímpares; a cor do par usa as duas
            if n % 2 == 0:
                self._pending = (parts["Y"], parts["C"])
                img.pixels[row] = ycc_to_rgb(parts["Y"], parts["C"], np.full(mode.width, 128.0))
            else:
                y0, cr = getattr(self, "_pending", (parts["Y"], np.full(mode.width, 128.0)))
                img.pixels[row - 1] = ycc_to_rgb(y0, cr, parts["C"])
                img.pixels[row] = ycc_to_rgb(parts["Y"], cr, parts["C"])


def decode_audio(audio, rate) -> list[Image]:
    """Decodifica um áudio inteiro (ex.: WAV gravado) e devolve as imagens completas."""
    dec, out = Decoder(rate), []
    for i in range(0, len(audio), 4096):
        for ev in dec.feed(audio[i:i + 4096]):
            if ev[0] == "done":
                out.append(ev[1])
    tail = np.zeros(int(rate * 2), np.float32)
    for ev in dec.feed(tail):
        if ev[0] == "done":
            out.append(ev[1])
    return out
