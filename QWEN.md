# LeanDeep 3.5 System - Technical Specification

## Overview
LeanDeep 3.5 is an advanced text analysis system that combines hierarchical marker detection with multidimensional context analysis. The system integrates a stable four-level marker hierarchy (ATO→SEM→CLU→MEMA) with the Resonance Framework 2.0 (RF2.0) for deeper contextual understanding.

## Core Architecture

### Four-Level Marker Hierarchy
The system follows a bottom-up aggregation principle:

1. **ATO_ (Atomic Markers)**: Primitive signal detection (tokens, emojis, regex patterns)
2. **SEM_ (Semantic Markers)**: Combination of ATO markers into meaningful micro-patterns
3. **CLU_ (Cluster Markers)**: Aggregation of thematic SEM markers over time/windows
4. **MEMA_ (Meta-Analysis Markers)**: Analysis of dynamic patterns across multiple clusters

### Resonance Framework 2.0 (RF2.0)
A multidimensional context layer that adds:
- **RF_LEVELS**: Eight developmental stages (L1-STONE to L8-COSMOS)
- **RF_TIME_INTENSITY**: Temporal and emotional intensity dimensions
- **RF_BRIDGE**: Integration matrix combining hierarchical markers with context

## Data Model
Each marker follows a consistent JSON schema:
- `id`: Unique identifier with four-letter prefix
- `frame`: Four-sided description (signal, concept, pragmatics, narrative)
- `examples`: At least 5 diverse examples
- One structure block: `pattern`, `composed_of`, or `detect_class`
- Optional `metadata` block for runtime logic

## Version Evolution
- **v3.1**: Foundation with four-level architecture
- **v3.2**: Four-letter prefixes and telemetry introduction
- **v3.3**: Formal composition rules and flexible metadata
- **v3.4**: Intuition markers with stateful logic
- **v3.5**: Integration of Resonance Framework 2.0

## Intuition Markers (v3.4+)
Stateful CLU markers with:
- Three states: `provisional`, `confirmed`, `decayed`
- Online learning via `ewma_precision`
- Bias protection mechanisms

## Integration Mechanisms
- **Contextualization**: "Stage colors the marker" - standard markers get meaning through developmental stage
- **Dynamic Coupling**: Boosts and guards that influence scoring in runtime
- **RF_BRIDGE**: Matrix rules combining standard markers with RF context

## Development Guidelines
- All SEM markers must compose of at least 2 distinct ATO markers (except with justification)
- Use four-letter prefixes consistently (ATO_, SEM_, CLU_, MEMA_)
- Implement proper examples for each marker (minimum 5 diverse examples)
- Leverage metadata block for runtime logic without schema changes
- Follow the integration patterns for RF2.0 context

## Key Concepts
- **Manifestation Formula**: [STAGE] × [MARKER-TYPE] × [TIME-REFERENCE] × [INTENSITY] = MANIFESTATION
- **Bottom-up Aggregation**: Lower-level markers trigger higher-level analysis
- **Contextualization**: Meaning depends on developmental stage and context
- **Dynamic Runtime**: Markers can influence each other's scoring at runtime

## License
The LeanDeep 3.5 system is licensed under Creative Commons BY-NC-SA 4.0 (Non-Commercial).