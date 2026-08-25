#!/usr/bin/env python3
"""
Sniffer serial em hexadecimal — o que o chat esconde.

Quando aparece "lixo" na tela do chat, nao da para saber o que aconteceu: o
decode UTF-8 transforma qualquer byte invalido no mesmo caractere. Aqui os
bytes aparecem crus, e o script conclui se o problema e eletrico ou de baud.

Sem --porta ele acha o USB-i485 sozinho pelo VID do chip FTDI, porque o nome
da porta muda de uma replugada para outra.

Uso:
    python sniffer.py --segundos 120
        Escuta SEM transmitir nada. Qualquer byte que apareca e ruido, nao
        dado. Use janela longa: ruido esporadico nao aparece em 10s, mas o
        chat acumula ao longo de minutos e acaba mostrando.

    python sniffer.py --enviar "PING-123" --repetir 20
        Transmite e mostra o que volta, em hexa. Serve para ver eco do proprio
        conversor e medir a razao entre bytes enviados e recebidos. Repetir
        aumenta a chance de provocar um erro intermitente.

    python sniffer.py --varrer
        Testa varias baud rates enquanto o OUTRO lado transmite sem parar, e
        indica qual delas produz texto legivel.
"""

import argparse
import sys
import time

import serial

from analise import diagnostico, formata_linha, fracao_printavel, hexdump
from portas import detectar

BAUDS = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]


def escuta(ser: serial.Serial, segundos: float, mostrar: bool) -> bytes:
    """Le tudo que chegar durante a janela de tempo, imprimindo em hexa.

    Marca o instante de cada rajada quando ha pausa entre elas. Ruido continuo
    e ruido periodico produzem o mesmo hexdump, mas causas diferentes — o
    intervalo entre rajadas e o que separa os dois.
    """
    inicio = time.monotonic()
    dados = bytearray()
    pendente = bytearray()
    offset = 0
    ultima = None

    while time.monotonic() - inicio < segundos:
        try:
            bloco = ser.read(ser.in_waiting or 1)
        except serial.SerialException as e:
            print(f"[porta caiu: {e}]")
            break

        if not bloco:
            continue

        agora = time.monotonic()
        if mostrar and (ultima is None or agora - ultima > 1.0):
            print(f"--- t = {agora - inicio:6.2f}s ---")
        ultima = agora

        dados.extend(bloco)
        if mostrar:
            pendente.extend(bloco)
            while len(pendente) >= 16:
                print(formata_linha(offset, bytes(pendente[:16])))
                del pendente[:16]
                offset += 16

    if mostrar and pendente:
        print(formata_linha(offset, bytes(pendente)))

    return bytes(dados)


def varrer(porta: str, segundos: float) -> None:
    """Abre a porta em cada baud e ve qual produz texto com mais sentido."""
    print("Varredura de baud rate.")
    print("Mantenha o OUTRO lado transmitindo texto sem parar durante o teste.")
    print(f"{len(BAUDS)} taxas x {segundos:.0f}s cada.\n")

    resultados = []
    for baud in BAUDS:
        try:
            with serial.Serial(porta, baud, timeout=0.1) as ser:
                time.sleep(0.1)
                ser.reset_input_buffer()
                dados = escuta(ser, segundos, mostrar=False)
        except serial.SerialException as e:
            print(f"  {baud:>6} bps   erro ao abrir: {e}")
            continue

        if not dados:
            print(f"  {baud:>6} bps   nada recebido")
            continue

        frac = fracao_printavel(dados)
        resultados.append((frac, baud, len(dados)))
        print(f"  {baud:>6} bps   {len(dados):6d} bytes   "
              f"{100 * frac:5.1f}% imprimivel")

    print()
    if not resultados:
        print("Nenhuma taxa recebeu nada. O outro lado estava transmitindo?")
        print("Se estava, o problema e fiacao, nao baud rate.")
        return

    frac, baud, _ = max(resultados)
    if frac > 0.90:
        print(f">>> {baud} bps produz texto limpo. Use essa taxa nos dois lados.")
    else:
        print(f">>> Melhor resultado: {baud} bps com apenas "
              f"{100 * frac:.0f}% imprimivel.")
        print("    Nenhuma taxa deu texto limpo — o problema nao e baud rate.")
        print("    Va para a fiacao: polaridade +/-, GND comum, modo do NPort.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Sniffer serial em hexadecimal")
    ap.add_argument("--porta", default="auto",
                    help="porta serial; 'auto' procura o chip FTDI do USB-i485")
    ap.add_argument("--baudrate", type=int, default=9600)
    ap.add_argument("--segundos", type=float, default=10.0,
                    help="duracao da escuta")
    ap.add_argument("--enviar", help="texto a transmitir antes de escutar")
    ap.add_argument("--repetir", type=int, default=1,
                    help="quantas vezes repetir o texto (ajuda a provocar o erro)")
    ap.add_argument("--varrer", action="store_true",
                    help="testa varias baud rates em sequencia")
    args = ap.parse_args()

    porta = detectar(args.porta)

    if args.varrer:
        varrer(porta, min(args.segundos, 3.0))
        return

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
        sys.exit(1)

    with ser:
        time.sleep(0.2)
        ser.reset_input_buffer()

        enviados = 0
        if args.enviar:
            carga = f"{args.enviar}\n".encode("utf-8")
            for _ in range(args.repetir):
                ser.write(carga)
                ser.flush()
            enviados = len(carga) * args.repetir
            print(f"Enviados {enviados} bytes "
                  f"({args.repetir}x {len(carga)}), em hexa:")
            hexdump(carga)
            print()
        else:
            print("Modo escuta pura — nada sera transmitido por este lado.")
            print("Deixe o outro lado parado tambem: o esperado e ZERO byte.")

        print(f"Escutando {porta} @ {args.baudrate} bps "
              f"por {args.segundos:.0f}s...\n")
        dados = escuta(ser, args.segundos, mostrar=True)

    if enviados and dados:
        print(f"\nrazao recebido/enviado: {len(dados) / enviados:.1f}x")

    diagnostico(dados, args.segundos, enviou=bool(args.enviar))


if __name__ == "__main__":
    main()
