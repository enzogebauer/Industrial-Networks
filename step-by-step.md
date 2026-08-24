# Passo a passo da prática — Computador A ↔ Computador B

Topologia desta montagem:

```
Computador A          USB-i485          NPort 5150         Computador B
  (serial)   --USB-->  (conversor) --RS-485--> (gateway) --Ethernet-->  (socket TCP)
chat_serial.py                       2 fios                        chat_tcp_nport.py
```

O Computador B **não instala driver nenhum**. O NPort fica em TCP Server mode e
faz tunelamento cru dos bytes seriais numa porta TCP — o B fala com ele por
socket, o que roda igual em Windows, Linux e macOS.

> **Por que TCP Server e não Real COM?** O modo Real COM cria uma COM virtual no
> Windows via driver proprietário da Moxa, e aí o B rodaria o mesmo
> `chat_serial.py` do A. Funciona, mas adiciona um driver ao conjunto de
> suspeitos quando algo falha. Os dois caminhos estão no `README.md`; **escolha
> um e siga inteiro**, porque eles exigem configurações diferentes no NPort.

Ordem importa: monte e energize o hardware antes de mexer em configuração, e
valide cada camada antes de subir pra próxima (barramento em silêncio → loopback
→ chat → Modbus). Pular direto pro Modbus e algo falhar deixa quatro suspeitos
ao mesmo tempo — fiação, modo do NPort, IP, baud rate. Os passos 6 e 7 existem
pra isolar isso.

---

## 1. Montar a fiação USB-i485 → NPort

Com tudo desenergizado:

- Deixe o pino **MOD (4)** do USB-i485 **sem ligação** → modo RS-485 half-duplex 2 fios
- **Rx+ (pino 2)** → **pino 3 do NPort** (Data+/B)
- **Rx- (pino 1)** → **pino 4 do NPort** (Data-/A)
- **GND (pino 5)** → **pino 5 do NPort**

Use par trançado. Não pule o GND — sem terra comum, os transceptores podem
ser danificados por diferença de potencial entre os dois lados.

O passo 6 confirma se esse par realmente é o par bidirecional do seu conversor.
Se lá o loopback só funcionar com a ponte Tx↔Rx, então Tx e Rx são pares
separados e é **Tx+/Tx-** que deve ir para o Data+/Data- do NPort, não Rx+/Rx-.

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

Deve aparecer marcada como chip FTDI (VID `0403`). Anote o nome da porta —
`/dev/ttyUSB0` no Linux, `/dev/cu.usbserial-XXX` no macOS, `COMx` no Windows.

Nas propriedades avançadas da porta, mude o **Latency Timer de 16 ms para 4 ms**.

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
| Baud rate / paridade / stop bits | `9600 8N1` (igual ao padrão do Python) |
| Operating Settings → Operation Mode | `TCP Server` |
| Operating Settings → Data Port | `4001` (padrão) |

**Interface é o campo que mais dá problema.** Em `RS-232` ou `RS-422/4-wire` o
transmissor do NPort fica ligado o tempo todo em vez de entrar em alta
impedância, e passa a disputar a linha com o conversor. O sintoma é lixo
contínuo, não texto embaralhado.

Anote o IP definido.

## 5. Ligar o NPort na rede e alcançar do Computador B

Conecte o NPort ao switch/roteador (ou direto no Computador B, com cabo
cross-over). Do Computador B:

```bash
python diagnostico.py --tcp <IP_do_NPort>:4001
```

Esperado: a porta 4001 aceita conexão. Se der **RECUSADO**, o NPort não está em
TCP Server mode — volte ao passo 4. Se der **TIMEOUT**, é rede: IP, faixa ou cabo.

> O Computador A **não precisa** enxergar o NPort pela rede. Ele fala só pela
> serial. Se o A estiver em outra rede, isso é normal e não é problema.

## 6. Validar a camada física

Três testes, nesta ordem. Cada um elimina um suspeito.

### 6a. O barramento está em silêncio?

Com **ninguém digitando nos dois lados**, escute em cada ponta:

```bash
# Computador A
python sniffer.py --porta /dev/cu.usbserial-130 --segundos 10

# Computador B
python sniffer_tcp.py --host <IP_do_NPort> --segundos 10
```

O resultado correto é **zero byte nos dois**. Se chegar qualquer coisa com
ninguém transmitindo, o problema é elétrico e nenhuma mudança de baud rate vai
resolver — vá para a tabela de troubleshooting antes de continuar.

### 6b. O conversor transmite e recebe?

No Computador A, **desconecte o fio que vai para o NPort** e ponteie
temporariamente Rx+ com Tx+ e Rx- com Tx- no bloco do USB-i485:

```bash
python sniffer.py --porta /dev/cu.usbserial-130 --enviar "PING-123" --segundos 5
```

| Resultado | Leitura |
|---|---|
| Volta `PING-123` limpo | Conversor e driver OK |
| Não volta nada | Conversor não está transmitindo — suspeite do pino MOD |
| Só volta com a ponte, nunca sem ela | Tx e Rx são pares **separados**: reveja o passo 1 |

Depois **desfaça a ponte** e refaça a fiação real com o NPort.

### 6c. Os bytes atravessam o caminho inteiro?

Com a fiação real montada, transmita de A e escute em B ao mesmo tempo:

```bash
# Computador B, primeiro
python sniffer_tcp.py --host <IP_do_NPort> --segundos 15

# Computador A, em seguida
python sniffer.py --porta /dev/cu.usbserial-130 --enviar "PING-123" --segundos 5
```

O `sniffer_tcp.py` deve mostrar exatamente `50 49 4E 47 2D 31 32 33 0A`. Se
chegar um volume muito maior que os 9 bytes enviados, a razão indica o fator de
divergência de baud rate — 90 bytes para 9 enviados significa baud do receptor
~10× acima da do transmissor.

## 7. Testar o link completo com o chat

```bash
# Computador A
python chat_serial.py --porta /dev/cu.usbserial-130 --nome A

# Computador B
python chat_tcp_nport.py --host <IP_do_NPort> --nome B
```

Digite uma mensagem em cada ponta — ela deve aparecer na outra. Esse é o teste
que prova USB + RS-485 + NPort + rede funcionando juntos, de ponta a ponta.

## 8. Rodar a aplicação Modbus

Com o chat validado:

```bash
# Computador A
python modbus_slave.py --porta /dev/cu.usbserial-130 --slave-id 1

# Computador B
python modbus_master.py tcp --host <IP_do_NPort> --slave-id 1

# testando escrita
python modbus_master.py tcp --host <IP_do_NPort> --setpoint 42
```

O mestre deve imprimir ciclo e temperatura a cada segundo. Confira no log do
escravo que o setpoint chegou.

---

## Troubleshooting rápido

| Sintoma | Causa provável | Onde resolver |
|---|---|---|
| Console web do NPort não abre | PC fora da faixa `192.168.127.x` | Passo 4 |
| `diagnostico.py` não lista porta nenhuma | Driver FTDI não instalado | Passo 3 |
| `--tcp` dá RECUSADO | NPort em Real COM em vez de TCP Server | Passo 4 |
| `--tcp` dá TIMEOUT | IP, faixa de rede ou cabo Ethernet | Passo 5 |
| Lixo contínuo com ninguém digitando | Ver bloco abaixo | Passo 6a |
| Loopback não retorna nada | Ponte errada ou MOD conectado | Passo 6b |
| Loopback retorna lixo | Baud rate divergente | Passo 4 |
| Chega muito mais byte do que foi enviado | Baud do NPort acima da do Python | Passo 4 |
| Chat não passa em nenhuma direção | Polaridade invertida (+/-) no par trançado | Passo 1 |
| Chat passa, Modbus não responde | NPort em RS-422/4-wire em vez de RS-485 2-wire | Passo 4 |
| Timeout intermitente no Modbus | Latency Timer ainda em 16 ms | Passo 3 |
| TCP conecta mas Modbus não decodifica nada | Esqueceu `framer=ModbusRtuFramer` no cliente TCP | `modbus_master.py` |

### Lixo contínuo mesmo sem ninguém transmitir

Esse sintoma não é baud rate — baud errada corrompe o que passa, não fabrica
byte do nada. Rode o passo 6a nas duas pontas e compare, porque **de que lado o
lixo aparece já elimina metade dos suspeitos**:

| Onde aparece | Provável causa |
|---|---|
| Só no B, A em silêncio | Par RS-485 aberto entre os dois. Cada ponta flutua sozinha e só o NPort tem bias fraco o bastante pra oscilar |
| Nos dois lados | Linha compartilhada flutuando, ou polaridade invertida |
| Só no A, B em silêncio | Ruído local no conversor ou cabo USB próximo de fonte chaveada |

Em RS-485 2 fios, quando ninguém transmite os dois drivers ficam em alta
impedância. Sem resistores de bias fail-safe a diferença de tensão fica em ~0 V,
o receptor oscila com ruído e inventa start bits indefinidamente. O NPort 5150
sai de fábrica com pull-up/pull-down de **150 kΩ**, fracos demais pra segurar a
linha; dentro da caixa há jumpers para terminação de 120 Ω e bias mais forte.
Antes de abrir o equipamento, confirme com multímetro a continuidade do par
entre o bloco do USB-i485 e os pinos 3, 4 e 5 do DB9 do NPort — fio solto no
terminal é a causa mais comum e a mais barata de descartar.
