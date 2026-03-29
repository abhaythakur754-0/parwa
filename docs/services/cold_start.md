# Cold Start Service

## Overview

The Cold Start Service bootstraps a new client's knowledge base with industry-specific FAQs and common support content, enabling immediate value from the PARWA AI support system.

**Location:** `shared/knowledge_base/cold_start.py`

## Features

- **Industry-Specific FAQ Templates**: Pre-built FAQ templates for various industries
- **Automatic Category Creation**: Organizes FAQs into logical categories
- **Document Ingestion Pipeline**: Seamless integration with Knowledge Base Manager
- **Company Personalization**: Personalizes FAQ content with company name
- **Activation Management**: Automatic or manual activation control

## Supported Industries

| Industry | Categories |
|----------|------------|
| E-commerce | orders, shipping, returns, payments |
| SaaS | account, billing, features |
| Healthcare | appointments, records, insurance |
| Finance | accounts, security, transactions |
| General | general |

## API Reference

### Classes

#### `ColdStartConfig`

Configuration for the Cold Start process.

```python
class ColdStartConfig(BaseModel):
    include_industry_faqs: bool = True      # Include industry-specific FAQs
    include_general_faqs: bool = True        # Include general FAQs
    include_escalation_rules: bool = True    # Include escalation rules
    max_faqs_per_category: int = 50          # Max FAQs per category (1-200)
    auto_activate: bool = True               # Auto-activate after bootstrap
```

#### `ColdStartResult`

Result of the cold start process.

```python
class ColdStartResult(BaseModel):
    company_id: UUID              # Company UUID
    industry: str                 # Industry type
    documents_ingested: int       # Number of documents ingested
    categories_created: int       # Number of categories created
    faqs_added: int              # Number of FAQs added
    status: str                   # Status: pending, completed, failed
    processing_time_ms: float     # Processing time in milliseconds
    errors: List[str]             # List of errors if any
    metadata: Dict[str, Any]      # Additional metadata
```

#### `IndustryType`

Enum for supported industry types.

```python
class IndustryType(str, Enum):
    ECOMMERCE = "ecommerce"
    SAAS = "saas"
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    EDUCATION = "education"
    HOSPITALITY = "hospitality"
    RETAIL = "retail"
    GENERAL = "general"
```

### Main Class: `ColdStart`

#### Initialization

```python
from shared.knowledge_base.cold_start import ColdStart, ColdStartConfig

cold_start = ColdStart(
    kb_manager=knowledge_base_manager,  # Optional: KB Manager instance
    config=ColdStartConfig(),           # Optional: Configuration
    company_id=uuid4(),                 # Optional: Company UUID
    embedding_fn=embedding_function,    # Optional: Embedding function
)
```

#### Methods

##### `bootstrap()`

Bootstrap knowledge base for a new company.

```python
result = cold_start.bootstrap(
    company_id=UUID,           # Required: Company UUID
    industry=IndustryType,     # Required: Industry type
    custom_faqs=List[Dict],    # Optional: Custom FAQs to add
    company_name=str,          # Optional: Company name for personalization
)
```

**Returns:** `ColdStartResult`

**Raises:** `ValueError` if company_id is None

##### `get_available_industries()`

Get list of available industry types.

```python
industries = cold_start.get_available_industries()
# Returns: ['ecommerce', 'saas', 'healthcare', 'finance', ...]
```

##### `get_industry_preview()`

Preview FAQ counts for an industry.

```python
preview = cold_start.get_industry_preview(IndustryType.ECOMMERCE)
# Returns: {'orders': 3, 'shipping': 3, 'returns': 3, 'payments': 3}
```

##### `get_stats()`

Get cold start statistics.

```python
stats = cold_start.get_stats()
# Returns:
# {
#     'cold_starts_completed': 5,
#     'total_documents_ingested': 100,
#     'average_documents_per_bootstrap': 20.0,
#     'available_industries': [...],
#     'config': {...}
# }
```

### Utility Functions

#### `create_cold_start_data()`

Create cold start data for a specific industry.

```python
from shared.knowledge_base.cold_start import create_cold_start_data, IndustryType

documents = create_cold_start_data(
    industry=IndustryType.SAAS,
    custom_questions=[
        {"question": "Q1", "answer": "A1", "category": "custom"}
    ]
)
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `include_industry_faqs` | bool | True | Include industry-specific FAQs |
| `include_general_faqs` | bool | True | Include general FAQs |
| `include_escalation_rules` | bool | True | Include escalation rules |
| `max_faqs_per_category` | int | 50 | Maximum FAQs per category (1-200) |
| `auto_activate` | bool | True | Auto-activate after bootstrap |

## Usage Examples

### Basic Bootstrap

```python
from uuid import uuid4
from shared.knowledge_base.cold_start import ColdStart, IndustryType

cold_start = ColdStart()
company_id = uuid4()

result = cold_start.bootstrap(
    company_id=company_id,
    industry=IndustryType.ECOMMERCE,
    company_name="MyStore"
)

print(f"Status: {result.status}")
print(f"Documents ingested: {result.documents_ingested}")
print(f"Processing time: {result.processing_time_ms:.2f}ms")
```

### With Custom FAQs

```python
custom_faqs = [
    {
        "question": "What is your warranty policy?",
        "answer": "We offer a 2-year warranty on all products.",
        "category": "warranty"
    },
    {
        "question": "Do you offer bulk discounts?",
        "answer": "Yes, contact sales@company.com for bulk orders.",
        "category": "sales"
    }
]

result = cold_start.bootstrap(
    company_id=company_id,
    industry=IndustryType.ECOMMERCE,
    custom_faqs=custom_faqs,
    company_name="MyStore"
)
```

### Minimal Bootstrap (No General FAQs)

```python
from shared.knowledge_base.cold_start import ColdStart, ColdStartConfig

config = ColdStartConfig(
    include_general_faqs=False,
    max_faqs_per_category=20
)

cold_start = ColdStart(config=config)
result = cold_start.bootstrap(
    company_id=company_id,
    industry=IndustryType.SAAS
)
```

### Integration with Knowledge Base Manager

```python
from shared.knowledge_base.kb_manager import KnowledgeBaseManager, KnowledgeBaseConfig
from shared.knowledge_base.cold_start import ColdStart, ColdStartConfig

# Create KB manager first
kb_manager = KnowledgeBaseManager(
    config=KnowledgeBaseConfig(),
    company_id=company_id,
    embedding_fn=your_embedding_function
)

# Pass to Cold Start
cold_start = ColdStart(
    kb_manager=kb_manager,
    config=ColdStartConfig()
)

result = cold_start.bootstrap(
    company_id=company_id,
    industry=IndustryType.FINANCE
)

# Now KB is ready for search
results = kb_manager.search("How do I track my order?")
```

## Error Handling

### Common Errors

| Error | Cause | Resolution |
|-------|-------|------------|
| `ValueError: Company ID is required` | company_id is None | Provide valid UUID |
| KB manager failure | KB manager throws exception | Check KB manager logs |
| Duplicate documents | Same content already exists | Handled automatically (skipped) |

### Error Example

```python
try:
    result = cold_start.bootstrap(
        company_id=None,  # This will raise
        industry=IndustryType.ECOMMERCE
    )
except ValueError as e:
    print(f"Validation error: {e}")

# Check result for errors
result = cold_start.bootstrap(
    company_id=company_id,
    industry=IndustryType.ECOMMERCE
)

if result.status == "failed":
    for error in result.errors:
        print(f"Error: {error}")
```

## Industry FAQ Templates

### E-commerce Example

```python
INDUSTRY_FAQS = {
    "ecommerce": {
        "orders": [
            {"question": "How do I track my order?", "answer": "..."},
            {"question": "Can I change my order after placing it?", "answer": "..."},
            {"question": "How do I cancel my order?", "answer": "..."},
        ],
        "shipping": [
            {"question": "What are the shipping options?", "answer": "..."},
            {"question": "Do you ship internationally?", "answer": "..."},
            {"question": "Why was my package returned to sender?", "answer": "..."},
        ],
        # ... more categories
    }
}
```

### Adding New Industry

To add a new industry, extend the `INDUSTRY_FAQS` dictionary and `IndustryType` enum:

```python
# In cold_start.py
INDUSTRY_FAQS["new_industry"] = {
    "category1": [
        {"question": "Q1", "answer": "A1"},
        # ...
    ],
}

class IndustryType(str, Enum):
    # ... existing types
    NEW_INDUSTRY = "new_industry"
```

## Best Practices

1. **Always provide company_id**: Required for proper data isolation
2. **Use company_name**: Improves FAQ personalization
3. **Add custom FAQs**: Include company-specific content
4. **Monitor statistics**: Track bootstraps and document counts
5. **Configure limits**: Set appropriate `max_faqs_per_category`

## Integration Points

- **Knowledge Base Manager**: Primary integration for document storage
- **Vector Store**: Embedding-based search capability
- **RAG Pipeline**: Retrieval-augmented generation support
- **FAQ Agent**: Direct use of loaded FAQs
