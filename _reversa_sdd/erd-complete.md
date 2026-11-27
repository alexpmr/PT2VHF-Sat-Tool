# ERD — Dados persistidos e trocados

> Reversa (Arquiteto), 27/11/2026. Não há banco de dados: a persistência é em arquivos JSON/CSV/WAV/PNG no
> perfil do usuário. O diagrama mostra as entidades lógicas e como se ligam. Atributos completos em
> [data-dictionary.md](data-dictionary.md).

```mermaid
erDiagram
  SETTINGS ||--o{ SATELITE_SELECIONADO : "lista selected"
  SETTINGS ||--|| ESTACAO : "lat/lon/alt, indicativo, locator"
  SETTINGS ||--o| PERFIL_RADIO : "cat_port, modelo, baud"
  SETTINGS ||--o| PERFIL_ROTOR : "modo, porta, rotctld"
  SETTINGS ||--o| PAINEL_WEB : "lan, porta, pin_hash, pin_salt"
  SATELITE ||--|| OMM : "NORAD_CAT_ID"
  SATELITE ||--o{ TRANSMISSOR : "norad_cat_id (SatNOGS)"
  SATELITE ||--o{ PASSAGEM : "calculada por estação"
  SATELITE_SELECIONADO }o--|| SATELITE : "NORAD"
  PASSAGEM ||--o{ PONTO_DOPPLER : "amostras az/el/range rate"
  PASSAGEM ||--o{ GRAVACAO_WAV : "sdr_recordings"
  PASSAGEM ||--o{ QUADRO_TELEMETRIA : "decodificado"
  PASSAGEM ||--o{ IMAGEM_SSTV : "sstv_images"
  MANIFESTO_UPDATE ||--o{ ARQUIVO_UPDATE : "files[]"

  SATELITE { int norad PK
             string nome
             string grupo }
  OMM { int NORAD_CAT_ID PK
        string EPOCH
        float MEAN_MOTION
        float ECCENTRICITY
        float INCLINATION }
  TRANSMISSOR { string uuid PK
                int norad_cat_id FK
                int downlink_low
                int uplink_low
                string mode
                bool invert }
  PASSAGEM { int norad FK
             datetime aos
             datetime tca
             datetime los
             float max_el }
  ESTACAO { float lat
            float lon
            float alt_m
            string indicativo }
  MANIFESTO_UPDATE { string product
                     string version
                     string date }
  ARQUIVO_UPDATE { string name
                   string url
                   int size
                   string sha256
                   string platform }
```

🟡 `PASSAGEM`, `PONTO_DOPPLER` e quadros de telemetria vivem em memória e em CSV/log; só gravações, imagens
e o diário são persistidos.
