#!/usr/bin/env python3
"""
Diagnostico da camada fisica. Rode isso ANTES de qualquer outro script.

Uso:
    python diagnostico.py                 # lista todas as portas seriais
    python diagnostico.py --porta COM3    # testa loopback na porta indicada
    python diagnostico.py --tcp 192.168.127.254:4001   # testa alcance do NPort
"""

import argparse
import socket
import sys
import time

import serial
import serial.tools.list_ports


def listar_portas() -> None:
    portas = list(serial.tools.list_ports.comports())
    if not portas:
        print("Nenhuma porta serial encontrada.")
        print("  - USB-i485 nao conectado, ou")
        print("  - driver FTDI (VCP) nao instalado")
        return

    print(f"{len(portas)} porta(s) encontrada(s):\n")
    for p in portas:
        print(f"  {p.device}")
        print(f"    descricao : {p.description}")
        print(f"    fabricante: {p.manufacturer or '-'}")
        print(f"    VID:PID   : {p.vid:04X}:{p.pid:04X}" if p.vid else "    VID:PID   : -")
        # O USB-i485 usa chip FTDI: VID 0x0403
        if p.vid == 0x0403:
            print("    >>> chip FTDI — provavelmente o USB-i485")
        print()


def teste_loopback(porta: str, baudrate: int) -> None:
    """
    Curto-circuite Rx+ com Tx+ e Rx- com Tx- no bloco de terminais do USB-i485.
    O que for escrito deve voltar identico.
    """
    print(f"Loopback em {porta} @ {baudrate} bps")
    print("Pre-requisito: Rx+ ligado a Tx+ e Rx- ligado a Tx- no USB-i485\n")

    try:
        with serial.Serial(porta, baudrate, timeout=2) as ser:
            time.sleep(0.2)
            ser.reset_input_buffer()

            enviado = b"PING-123\n"
            ser.write(enviado)
            recebido = ser.read(len(enviado))

            print(f"  enviado : {enviado!r}")
            print(f"  recebido: {recebido!r}")

            if recebido == enviado:
                print("\n  OK — camada fisica funcionando.")
            elif not recebido:
                print("\n  FALHA — nada voltou.")
                print("  Verifique a ponte Rx/Tx e se o MOD (pino 4) esta desconectado.")
            else:
                print("\n  FALHA — dados corrompidos.")
                print("  Baud rate provavelmente errada, ou ruido no barramento.")
    except serial.SerialException as e:
        print(f"  Erro ao abrir a porta: {e}")
        sys.exit(1)


def teste_tcp(destino: str) -> None:
    host, _, porta_txt = destino.partition(":")
    porta = int(porta_txt or 4001)

    print(f"Testando {host}:{porta}")

    # Ping TCP na porta de dados
    sock = socket.socket()
    sock.settimeout(3)
    try:
        sock.connect((host, porta))
        print(f"  OK — porta {porta} aceita conexao (NPort em TCP Server mode).")
    except socket.timeout:
        print(f"  TIMEOUT — host inalcancavel ou porta {porta} fechada.")
        print("  Verifique: IP do NPort, faixa da rede, cabo Ethernet.")
    except ConnectionRefusedError:
        print(f"  RECUSADO — o NPort responde, mas a porta {porta} nao esta escutando.")
        print("  Provavel: NPort esta em Real COM mode, nao em TCP Server mode.")
    finally:
        sock.close()

    # Console web
    web = socket.socket()
    web.settimeout(3)
    try:
        web.connect((host, 80))
        print(f"  Console web acessivel em http://{host} (senha padrao: moxa)")
    except OSError:
        print("  Console web (porta 80) nao respondeu.")
    finally:
        web.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Diagnostico do link serial/Ethernet")
    ap.add_argument("--porta", help="porta serial para teste de loopback")
    ap.add_argument("--baudrate", type=int, default=9600)
    ap.add_argument("--tcp", help="host:porta do NPort, ex.: 192.168.127.254:4001")
    args = ap.parse_args()

    if args.tcp:
        teste_tcp(args.tcp)
    elif args.porta:
        teste_loopback(args.porta, args.baudrate)
    else:
        listar_portas()


if __name__ == "__main__":
    main()
