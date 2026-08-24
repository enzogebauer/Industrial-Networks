# Passo a passo da prática — Computador A ↔ Computador B via RS-485 + Ethernet

Ordem importa: monte e energize o hardware antes de mexer em driver, e valide
cada camada antes de subir pra próxima (loopback → chat → Modbus). Pular direto
pro Modbus e algo falhar deixa três suspeitos ao mesmo tempo — fiação, IP do
NPort, baud rate. Os passos 6 e 7 existem pra isolar isso.

---

## 1. Montar a fiação USB-i485 → NPort

Com tudo desenergizado:

- Deixe o pino **MOD (4)** do USB-i485 **sem ligação** → modo RS-485 half-duplex 2 fios
- **Rx+ (pino 2)** → **pino 3 do NPort** (Data+/B)
- **Rx- (pino 1)** → **pino 4 do NPort** (Data-/A)
- **GND (pino 5)** → **pino 5 do NPort**

Use par trançado. Não pule o GND — sem terra comum, os transceptores podem
ser danificados por diferença de potencial entre os dois lados.

## 2. Energizar o NPort

Ligue a fonte 12–48 VDC no NPort.

- LED **Ready** verde fixo após alguns segundos → ok
- LED Ready piscando vermelho → conflito de IP ou falha de boot

Não conecte o cabo Ethernet ainda — resolva a alimentação primeiro.

## 3. Conectar o USB-i485 no Computador A

Plugue o cabo USB.

- **Linux:** driver `ftdi_sio` já é nativo no kernel
- **Windows/macOS:** instale o driver VCP da FTDI

Confirme a porta:

```bash
python diagnostico.py
```

Deve aparecer marcada como chip FTDI (VID `0403`). Nas propriedades avançadas
da porta, mude o **Latency Timer de 16 ms para 4 ms**.

## 4. Configurar o NPort pelo console web

Coloque um PC na mesma rede do NPort (faixa `192.168.127.x` se ainda estiver
no padrão de fábrica — se o console não abrir, é isso, ajuste o IP do seu PC
antes de insistir no cabo) e acesse:

```
http://192.168.127.254   (senha: moxa)
```

Defina:

| Campo | Valor |
|---|---|
| Serial Settings → Interface | `RS-485 2-wire` |
| Baud rate / paridade / stop bits | `9600 8N1` (igual ao Python, pra começar) |
| Operating Settings → Operation Mode | `Real COM` |

Anote o IP definido.

## 5. Ligar o NPort na rede definitiva e o Computador B

Conecte o NPort ao switch/roteador (ou direto no Computador B, com cabo
cross-over). No Computador B:

1. Instale o **NPort Windows Driver Manager**
2. Aponte para o IP do NPort
3. Mapeie a porta serial 1 para uma COM virtual (ex.: `COM5`)

Ela deve aparecer no Gerenciador de Dispositivos como qualquer outra porta serial.

## 6. Validar a camada física

No Computador A, ponteie **temporariamente** Rx+ com Tx+ e Rx- com Tx- no
bloco do USB-i485:

```bash
python diagnostico.py --porta /dev/ttyUSB0
```

O texto enviado deve voltar idêntico. Depois **desfaça a ponte** e refaça a
fiação real com o NPort (passo 1).

De qualquer máquina na rede, confirme que a porta de dados do NPort responde:

```bash
python diagnostico.py --tcp <IP_do_NPort>:4001
```

## 7. Testar o link completo com o chat

```bash
# Computador A
python chat_serial.py --porta /dev/ttyUSB0 --nome A

# Computador B
python chat_serial.py --porta COM5 --nome B
```

Mesma baud rate nos dois lados. Digite uma mensagem em cada ponta — ela deve
aparecer na outra. Esse é o teste que prova USB + RS-485 + NPort + rede
funcionando juntos, de ponta a ponta.

## 8. Rodar a aplicação Modbus

Com o chat validado:

```bash
# Computador A
python modbus_slave.py --porta /dev/ttyUSB0 --slave-id 1

# Computador B
python modbus_master.py serial --porta COM5 --slave-id 1

# testando escrita
python modbus_master.py serial --porta COM5 --setpoint 42
```

O mestre deve imprimir ciclo e temperatura a cada segundo. Confira no log do
escravo que o setpoint chegou.

---

## Troubleshooting rápido

| Sintoma | Causa provável | Onde resolver |
|---|---|---|
| Console web do NPort não abre | PC fora da faixa `192.168.127.x` | Passo 4 |
| `diagnostico.py` não lista porta nenhuma | Driver FTDI não instalado | Passo 3 |
| Loopback não retorna nada | Ponte errada ou MOD conectado | Passo 6 |
| Loopback retorna lixo | Baud rate divergente | Passo 4 |
| Chat não passa em nenhuma direção | Polaridade invertida (+/-) no par trançado | Passo 1 |
| Chat passa, Modbus não responde | NPort em RS-422/4-wire em vez de RS-485 2-wire | Passo 4 |
| Timeout intermitente no Modbus | Latency Timer ainda em 16 ms | Passo 3 |
| TCP conecta mas Modbus não decodifica nada | Esqueceu `framer=ModbusRtuFramer` no cliente TCP | código `modbus_master.py` |
