# Chatbot Telegram com Selenium Remoto

Este projeto utiliza Selenium conectado a um container Docker para extração de dados de notas fiscais.

## Configuração do Ambiente

### 1. Variáveis de Ambiente

Configure o arquivo `.env` com suas credenciais:

```env
# Telegram Bot Token
BOT_TOKEN=seu_bot_token_aqui

# Selenium Remote URL
SELENIUM_REMOTE_URL=http://selenium:4444
```

### 2. Executar com Docker

Para iniciar os containers:

```bash
docker-compose up --build
```

Isso irá:
- Iniciar o container Selenium na porta 4444
- Construir e iniciar o container do bot
- Configurar a conexão entre os containers

### 3. Testar Conexão Selenium

Para testar se a conexão com o Selenium remoto está funcionando:

```bash
# Executar dentro do container do bot
docker exec -it bot python test_selenium.py
```

## Arquitetura

- **selenium container**: Executa o navegador Chrome em modo headless
- **bot container**: Executa o bot Telegram e se conecta ao Selenium remoto
- **read_qrcode.py**: Modificado para usar `webdriver.Remote()` em vez de `webdriver.Chrome()`

## Como Funciona

1. O bot recebe uma imagem de QR code
2. O QR code é decodificado para obter a URL da nota fiscal
3. O bot se conecta ao Selenium remoto via HTTP
4. O Selenium abre a URL e extrai os dados da página
5. Os dados são processados e retornados ao usuário

## Solução de Problemas

### Selenium não conecta
- Verifique se o container Selenium está rodando: `docker ps`
- Verifique os logs: `docker logs selenium`
- Teste a conexão manualmente: `curl http://localhost:4444/wd/hub/status`

### Bot não inicia
- Verifique se o BOT_TOKEN está correto no `.env`
- Verifique os logs do bot: `docker logs bot`
- Certifique-se de que o container Selenium está rodando antes do bot
