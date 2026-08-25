#!/usr/bin/env python3
"""
Chat bidirecional sobre porta serial. O MESMO script roda nos dois lados:

  Computador A: porta COM real do USB-i485       (ex.: /dev/ttyUSB0, COM3)
  Computador B: porta COM virtual do NPort       (ex.: COM5, /dev/ttyr00)

Uso:
    python chat_serial.py --porta /dev/ttyUSB0 --nome A
    python chat_serial.py --porta COM5 --nome B

Os dois lados precisam da MESMA baud rate. Se um estiver em 9600 e o outro
em 19200, chegam bytes, mas embaralhados — esse e o sintoma classico de
"aparecem caracteres estranhos".
"""

import argparse
import sys
import threading

import serial

from portas import detectar


def leitor(ser: serial.Serial, parar: threading.Event) -> None:
    """Thread de recepcao: le linha a linha e imprime."""
    buffer = bytearray()
    while not parar.is_set():
        try:
            dados = ser.read(ser.in_waiting or 1)
        except serial.SerialException:
            print("\n[porta fechada]")
            parar.set()
            return

        if not dados:
            continue

        buffer.extend(dados)
        while b"\n" in buffer:
            linha, _, resto = buffer.partition(b"\n")
            buffer = bytearray(resto)
            texto = linha.decode("utf-8", errors="replace").rstrip("\r")
            # \r limpa a linha do prompt antes de imprimir a mensagem recebida
            print(f"\r<< {texto}\n>> ", end="", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", default="auto",
                    help="porta serial; 'auto' procura o chip FTDI do USB-i485")
    ap.add_argument("--baudrate", type=int, default=9600)
    ap.add_argument("--nome", default="?", help="identificador deste lado")
    args = ap.parse_args()

    porta = detectar(args.porta)

    # 8N1: 8 data bits, sem paridade, 1 stop bit.
    # Esse e o "10 bits" que o ADAM-4520 chama de formato padrao
    # (1 start + 8 dados + 1 stop).
    try:
        ser = serial.Serial(
            port=porta,
            baudrate=args.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )
    except serial.SerialException as e:
        print(f"Erro ao abrir {porta}: {e}")
        print("Rode 'python diagnostico.py' para listar as portas disponiveis.")
        sys.exit(1)

    print(f"Conectado em {porta} @ {args.baudrate} bps (8N1)")
    print("Digite e pressione Enter. Ctrl+C para sair.\n")

    parar = threading.Event()
    t = threading.Thread(target=leitor, args=(ser, parar), daemon=True)
    t.start()

    try:
        while True:
            texto = input(">> ")
            if not texto:
                continue
            ser.write(f"[{args.nome}] {texto}\n".encode("utf-8"))
            # flush garante que o byte saiu do buffer do SO para o driver FTDI
            ser.flush()
    except (KeyboardInterrupt, EOFError):
        print("\nEncerrando.")
    finally:
        parar.set()
        ser.close()


if __name__ == "__main__":
    main()
