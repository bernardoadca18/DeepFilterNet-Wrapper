# DeepFilterNet Docker

Dockerização do DeepFilterNet para facilitar a execução e utilização da ferramenta de redução de ruído em arquivos de áudio.

## Requisitos

- Docker 24.0+
- Docker Compose v2
- NVIDIA Container Toolkit
- GPU com suporte a CUDA 11.8+
- Driver NVIDIA atualizado

## Instalação do NVIDIA Container Toolkit

```bash
# Ubuntu/Debian
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

## Uso Rápido

```bash
cd docker
docker compose up -d
```

Acesse http://localhost no navegador.

## Estrutura

```
docker/
├── Dockerfile              # Multi-stage build
├── docker-compose.yml      # Orquestração
├── nginx.conf              # Proxy reverso
└── .dockerignore           # Arquivos ignorados

app/
├── backend/
│   ├── main.py             # API FastAPI
│   ├── requirements.txt    # Dependências
│   └── entrypoint.sh       # Script de inicialização
└── frontend/
    ├── index.html          # Interface web
    ├── style.css           # Estilos
    └── app.js              # Lógica frontend
```

## API Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/enhance` | Upload e processamento de arquivo WAV |
| GET | `/api/status/{job_id}` | Status do processamento |
| GET | `/api/download/{job_id}` | Download do áudio processado |
| GET | `/api/download/{job_id}/original` | Download do áudio original |
| DELETE | `/api/job/{job_id}` | Remove job e arquivos |
| GET | `/api/health` | Healthcheck |

## Exemplo de Uso via CLI

```bash
# Upload e processamento
JOB_ID=$(curl -s -X POST http://localhost:8994/api/enhance \
  -F "file=@noisy_audio.wav" | jq -r '.job_id')

# Verificar status
curl http://localhost:8994/api/status/$JOB_ID | jq

# Download do resultado
curl -O http://localhost:8994/api/download/$JOB_ID
```

## Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `MODEL_CACHE_DIR` | `/app/model_cache` | Diretório de cache dos modelos |
| `TEMP_FILES_DIR` | `/app/temp_files` | Arquivos temporários |
| `DEFAULT_MODEL` | `DeepFilterNet3` | Modelo padrão |
| `LOG_LEVEL` | `INFO` | Nível de log |

## Build Manual

```bash
cd docker
docker build -t deepfilternet:latest -f Dockerfile ..
```

## Executar Apenas Backend

```bash
docker run -d \
  --name deepfilternet-backend \
  --gpus all \
  -p 8994:8994 \
  -v deepfilternet-cache:/app/model_cache \
  deepfilternet:latest
```

## Logs

```bash
# Ver logs
docker compose logs -f

# Apenas backend
docker compose logs -f backend
```

## Troubleshooting

### GPU não detectada

```bash
# Verificar se a GPU está disponível
docker run --rm --gpus all nvidia/cuda:11.8-base nvidia-smi
```

### Modelo não baixa

O modelo DeepFilterNet3 é baixado automaticamente no primeiro uso (~150MB). Verifique a conexão com a internet.

### Erro de memória

Para arquivos grandes, pode ser necessário aumentar a memória do container:

```yaml
deploy:
  resources:
    limits:
      memory: 4G
```

## Parar e Limpar

```bash
# Parar containers
docker compose down

# Remover volumes
docker compose down -v

# Remover imagens
docker rmi deepfilternet:latest
```

## Modelo Utilizado

Por padrão, utiliza **DeepFilterNet3**, a versão mais recente com melhor qualidade de redução de ruído. Os modelos disponíveis são:

- `DeepFilterNet3` - Melhor qualidade (padrão)
- `DeepFilterNet2` - Menor latência

Para usar outro modelo, altere a variável `DEFAULT_MODEL` no `docker-compose.yml`.

## Licença

DeepFilterNet é dual-licensed sob MIT ou Apache-2.0. Veja [LICENSE](../LICENSE) para mais detalhes.
