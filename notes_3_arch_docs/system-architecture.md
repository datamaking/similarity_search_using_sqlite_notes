```mermaid

flowchart TD
    User["User (Browser)"]
    WebServer["Django Web Server"]
    AuthSystem["Authentication System"]
    SearchEngine["Similarity Search Engine"]
    VectorDB1["ADMIN Vector DB"]
    VectorDB2["IT Vector DB"]
    VectorDB3["FINANCE Vector DB"]
    VectorDB4["HR Vector DB"]
    EmbeddingModel["Sentence Transformer Model"]
    SQLiteVec["SQLite-Vec Extension"]
    FallbackEngine["Fallback Similarity Engine"]
    
    User <--> WebServer
    WebServer --> AuthSystem
    WebServer --> SearchEngine
    SearchEngine --> VectorDB1
    SearchEngine --> VectorDB2
    SearchEngine --> VectorDB3
    SearchEngine --> VectorDB4
    SearchEngine --> EmbeddingModel
    SearchEngine --> SQLiteVec
    SearchEngine --> FallbackEngine
    
    subgraph "Vector Databases"
        VectorDB1
        VectorDB2
        VectorDB3
        VectorDB4
    end
    
    subgraph "Search Components"
        EmbeddingModel
        SQLiteVec
        FallbackEngine
    end
    
    classDef primary fill:#f9f,stroke:#333,stroke-width:2px
    classDef secondary fill:#bbf,stroke:#333,stroke-width:1px
    classDef tertiary fill:#fbb,stroke:#333,stroke-width:1px
    
    class WebServer,SearchEngine primary
    class AuthSystem,EmbeddingModel secondary
    class VectorDB1,VectorDB2,VectorDB3,VectorDB4,SQLiteVec,FallbackEngine tertiary