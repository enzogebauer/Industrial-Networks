#!/usr/bin/env python3
"""
Analise de bytes crus, compartilhada por sniffer.py e sniffer_tcp.py.

Por que existe: o chat imprime tudo com decode("utf-8", errors="replace"), e
isso apaga justamente a informacao que importa. Um 0x00, um 0xFF e um 0x93
viram o mesmo caractere de substituicao na tela — mas cada um aponta para uma
causa diferente no barramento. Aqui o byte aparece cru.
"""

import collections

PRINTAVEIS = set(range(0x20, 0x7F)) | {0x09, 0x0A, 0x0D}


def formata_linha(offset: int, bloco: bytes) -> str:
    """Uma linha de hexdump: offset, 16 bytes em hexa, e o texto ao lado."""
    hexa = " ".join(f"{b:02X}" for b in bloco)
    texto = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in bloco)
    return f"{offset:06X}  {hexa:<47}  |{texto}|"


def hexdump(dados: bytes, offset_inicial: int = 0) -> None:
    for i in range(0, len(dados), 16):
        print(formata_linha(offset_inicial + i, dados[i:i + 16]))


def transicoes(b: int) -> int:
    """Quantas vezes o bit muda de valor dentro do byte.

    Metrica que separa ruido de baud rate errada. Amostrar um sinal na baud
    errada estica cada bit por varias amostras, entao os bytes saem com poucas
    transicoes (0xF0, 0xC0, 0x7E, 0x3E...). Texto ASCII fica entre 3 e 4, e
    ruido eletrico aleatorio fica em torno de 3.5.
    """
    bits = f"{b:08b}"
    return sum(1 for i in range(7) if bits[i] != bits[i + 1])


def fracao_printavel(dados: bytes) -> float:
    return sum(1 for b in dados if b in PRINTAVEIS) / len(dados)


def diagnostico(dados: bytes, segundos: float, enviou: bool) -> None:
    """Interpreta o que chegou.

    A conclusao que interessa e binaria: o problema esta na camada eletrica ou
    na configuracao de baud rate. Sao consertos em lugares diferentes, e mexer
    em baud rate quando o problema e eletrico nao muda nada.
    """
    print()
    print("=" * 64)
    print("DIAGNOSTICO")
    print("=" * 64)

    if not dados:
        if enviou:
            print("Nada voltou.")
            print()
            print("  Se o outro lado estava transmitindo, os suspeitos sao:")
            print("    - par +/- invertido entre os dois equipamentos")
            print("    - fio aberto, ou GND sem ligacao entre os dois lados")
            print("    - baud rate muito distante nas duas pontas")
            print("  Se ninguem estava transmitindo, esse teste nao diz nada.")
        else:
            print(f"Nenhum byte nesta janela de {segundos:.0f}s.")
            print()
            print("  Isso ainda NAO prova que o barramento esta limpo. Ruido")
            print("  esporadico — poucos bytes por minuto — passa despercebido")
            print("  numa janela curta, e e exatamente o que o chat acumula ao")
            print("  ficar aberto por varios minutos.")
            if segundos < 60:
                print()
                print("  >>> Se o chat mostra lixo mas este teste nao, repita")
                print("      com --segundos 120 antes de concluir qualquer coisa.")
        return

    taxa = len(dados) / segundos
    print(f"{len(dados)} bytes em {segundos:.0f}s  ({taxa:.0f} bytes/s)")

    hist = collections.Counter(dados)
    print()
    print("bytes mais frequentes:")
    for b, n in hist.most_common(5):
        print(f"  0x{b:02X}   {n:7d}   {100 * n / len(dados):5.1f}%")

    frac = fracao_printavel(dados)
    trans = sum(transicoes(b) for b in dados) / len(dados)
    print()
    print(f"  ASCII imprimivel : {100 * frac:.0f}%")
    print(f"  transicoes/byte  : {trans:.1f}"
          "   (texto ~3-4, ruido ~3.5, baud errada ~1-2)")

    dominante, n_dom = hist.most_common(1)[0]
    frac_dom = n_dom / len(dados)

    print()
    if frac > 0.90:
        print(">>> Dados legiveis. A camada fisica esta OK.")
        return

    if not enviou:
        print(">>> Bytes chegando com NINGUEM transmitindo.")
        print("    O problema e ELETRICO, nao de baud rate. Trocar a baud")
        print("    nas duas pontas nao vai mudar nada aqui.")
        print()
        print("    Suspeitos, nessa ordem:")
        print("      1. linha flutuando — em RS-485 2 fios, com os dois drivers")
        print("         em alta impedancia e sem bias fail-safe, a diferenca de")
        print("         tensao fica em ~0V e o receptor oscila com ruido,")
        print("         inventando start bits indefinidamente")
        print("      2. o outro lado nao esta em alta impedancia — NPort em")
        print("         RS-232 ou RS-422/4-wire em vez de RS-485 2-wire deixa o")
        print("         transmissor sempre ligado, disputando a linha")
        print("      3. par +/- invertido entre os dois equipamentos")
        return

    if dominante in (0x00, 0xFF) and frac_dom > 0.30:
        alvo = "0x00" if dominante == 0x00 else "0xFF"
        print(f">>> Fluxo dominado por {alvo} ({100 * frac_dom:.0f}%).")
        print("    Nao e dado corrompido, e a linha presa em um nivel so:")
        print("      - 0x00 predominante: polaridade invertida, ou condicao de")
        print("        break (linha em espaco continuo)")
        print("      - 0xFF predominante: linha em repouso alto sendo lida como")
        print("        dado, tipico de receptor sem sinal valido")
        print("    Confira a polaridade +/- e o GND antes de mexer em baud.")
        return

    if trans < 2.2:
        print(">>> Assinatura de BAUD RATE divergente.")
        print("    Poucas transicoes por byte quer dizer bits esticados: o")
        print("    receptor esta amostrando em ritmo diferente do transmissor.")
        print("    Compare a razao de volume: se voce enviou N bytes e chegaram")
        print("    ~10N, a baud do receptor esta ~10x acima da do transmissor.")
        return

    print(">>> Ruido eletrico sem estrutura de dado reconhecivel.")
    print("    Transicoes por byte na faixa do aleatorio. Trate como problema")
    print("    de fiacao: polaridade, GND comum, terminacao e bias.")
