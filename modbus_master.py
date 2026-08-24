#!/usr/bin/env python3
"""
Computador B — mestre Modbus. Consulta o escravo que roda no Computador A.

Dois transportes:

  serial  ->  usa a COM virtual criada pelo driver Real COM da MOXA
              python modbus_master.py serial --porta COM5

  tcp     ->  fala direto com o NPort em TCP Server mode, sem driver
              python modbus_master.py tcp --host 192.168.127.254

ATENCAO ao transporte tcp: o NPort faz tunelamento CRU dos bytes seriais.
Ou seja, o que trafega ainda e Modbus RTU (com CRC), so que dentro de um
socket TCP. Isso NAO e Modbus TCP (que usa cabecalho MBAP e nao tem CRC).
Por isso passamos framer=ModbusRtuFramer no cliente TCP. Trocar isso e
o erro mais comum nessa montagem — os dois lados conectam, mas nada responde.
"""

import argparse
import time

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.framer.rtu_framer import ModbusRtuFramer


def montar_cliente(args):
    if args.transporte == "serial":
        return ModbusSerialClient(
            port=args.porta,
            baudrate=args.baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=2,
        )
    return ModbusTcpClient(
        host=args.host,
        port=args.tcp_port,
        framer=ModbusRtuFramer,  # RTU encapsulado, nao Modbus TCP
        timeout=2,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("transporte", choices=["serial", "tcp"])
    ap.add_argument("--porta", help="porta COM virtual (transporte serial)")
    ap.add_argument("--baudrate", type=int, default=9600)
    ap.add_argument("--host", default="192.168.127.254")
    ap.add_argument("--tcp-port", type=int, default=4001)
    ap.add_argument("--slave-id", type=int, default=1)
    ap.add_argument("--setpoint", type=int, help="escreve um valor no holding register 0")
    args = ap.parse_args()

    if args.transporte == "serial" and not args.porta:
        ap.error("transporte serial exige --porta")

    client = montar_cliente(args)

    if not client.connect():
        print("Nao conectou.")
        print("  serial: confira se a COM virtual do NPort existe")
        print("  tcp   : confira se o NPort esta em TCP Server mode")
        return

    print(f"Conectado ({args.transporte}). Consultando escravo id={args.slave_id}.\n")

    try:
        if args.setpoint is not None:
            resp = client.write_register(0, args.setpoint, slave=args.slave_id)
            if resp.isError():
                print(f"Erro ao escrever: {resp}")
            else:
                print(f"Setpoint {args.setpoint} escrito no holding register 0.\n")

        while True:
            # Le 2 input registers a partir do endereco 0
            resp = client.read_input_registers(0, 2, slave=args.slave_id)

            if resp.isError():
                # Erro de protocolo (excecao Modbus) ou timeout
                print(f"  erro: {resp}")
            else:
                ciclo, temp_decimos = resp.registers
                print(f"  ciclo={ciclo:5d}   temperatura={temp_decimos / 10:.1f} C")

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nEncerrando.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
