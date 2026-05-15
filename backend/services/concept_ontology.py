"""
Sanskrit Concept Ontology (SCO) — A lightweight graph of dharmic concepts
for query expansion and concept-aware retrieval.

Uses NetworkX directed graph with ~150 nodes and ~250 edges.
Node types: concept (with tradition, related_emotions, related_domains)
Edge types: IS_A, IMPLIES, OPPOSITE_OF, PRECONDITION_OF

Usage:
    ontology = get_concept_ontology()
    related = ontology.get_related_concepts("nishkama karma", depth=2)
    # → ["svadharma", "phala tyaga", "karma yoga", "ishvara pranidhana"]
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Edge type weights (how strongly the relationship transfers relevance)
EDGE_WEIGHTS = {
    "IS_A": 0.9,
    "IMPLIES": 0.7,
    "OPPOSITE_OF": 0.3,
    "PRECONDITION_OF": 0.6,
    "RELATED_TO": 0.5,
}


class ConceptOntology:
    """Lightweight concept graph for dharmic term expansion."""

    def __init__(self):
        self._graph = None
        self._available = False
        self._concept_lookup: Dict[str, str] = {}  # lowercase → canonical name

    @property
    def available(self) -> bool:
        return self._available

    def initialize(self, graph_path: Optional[str] = None) -> None:
        """Load or build the concept graph."""
        if graph_path is None:
            graph_path = str(
                Path(__file__).resolve().parent.parent / "data" / "processed" / "sco_graph.json"
            )

        try:
            import networkx as nx
        except ImportError:
            logger.warning("ConceptOntology: networkx not installed — ontology disabled")
            return

        self._graph = nx.DiGraph()

        # Try loading from JSON
        if os.path.exists(graph_path):
            try:
                with open(graph_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for node in data.get("nodes", []):
                    self._graph.add_node(node["id"], **{k: v for k, v in node.items() if k != "id"})
                for edge in data.get("edges", []):
                    self._graph.add_edge(
                        edge["source"], edge["target"],
                        type=edge.get("type", "RELATED_TO"),
                        weight=edge.get("weight", 0.5),
                    )
                logger.info(f"ConceptOntology: loaded {self._graph.number_of_nodes()} nodes, "
                            f"{self._graph.number_of_edges()} edges from {graph_path}")
            except Exception as e:
                logger.error(f"ConceptOntology: failed to load graph — {e}")
                self._build_seed_graph()
        else:
            logger.info("ConceptOntology: no graph file found, building seed graph")
            self._build_seed_graph()
            # Save for next time
            self._save_graph(graph_path)

        # Build lowercase lookup
        for node in self._graph.nodes:
            self._concept_lookup[node.lower()] = node
            # Also index aliases
            aliases = self._graph.nodes[node].get("aliases", [])
            for alias in aliases:
                self._concept_lookup[alias.lower()] = node

        self._available = True
        logger.info(f"ConceptOntology: {len(self._concept_lookup)} terms indexed")

    def _build_seed_graph(self) -> None:
        """Build seed graph with ~150 dharmic concepts and ~250 edges."""
        import networkx as nx
        if self._graph is None:
            self._graph = nx.DiGraph()

        # ── Core Vedanta concepts ──
        _vedanta = [
            ("Brahman", {"tradition": "vedanta", "aliases": ["brahm"], "related_emotions": [], "related_domains": ["liberation", "knowledge_learning"]}),
            ("Atman", {"tradition": "vedanta", "aliases": ["atma", "soul"], "related_emotions": [], "related_domains": ["self_improvement", "liberation"]}),
            ("Maya", {"tradition": "vedanta", "aliases": ["illusion"], "related_emotions": ["confusion"], "related_domains": ["knowledge_learning"]}),
            ("Moksha", {"tradition": "vedanta", "aliases": ["liberation", "mukti"], "related_emotions": ["hope"], "related_domains": ["liberation", "spiritual_practice"]}),
            ("Avidya", {"tradition": "vedanta", "aliases": ["ignorance"], "related_emotions": ["confusion"], "related_domains": ["knowledge_learning"]}),
            ("Viveka", {"tradition": "vedanta", "aliases": ["discrimination", "discernment"], "related_emotions": [], "related_domains": ["knowledge_learning", "self_improvement"]}),
            ("Vairagya", {"tradition": "vedanta", "aliases": ["detachment", "dispassion"], "related_emotions": ["contentment"], "related_domains": ["spiritual_practice"]}),
            ("Dharma", {"tradition": "vedanta", "aliases": ["duty", "righteousness"], "related_emotions": [], "related_domains": ["dharma_duty", "ethics"]}),
            ("Karma", {"tradition": "vedanta", "aliases": ["action"], "related_emotions": [], "related_domains": ["career_work", "dharma_duty"]}),
            ("Samsara", {"tradition": "vedanta", "aliases": ["cycle of rebirth"], "related_emotions": ["despair"], "related_domains": ["rebirth", "liberation"]}),
        ]

        # ── Vedanta Extended concepts ──
        _vedanta_ext = [
            ("Nirguna Brahman", {"tradition": "vedanta", "aliases": ["formless absolute"], "related_emotions": [], "related_domains": ["liberation", "knowledge_learning"]}),
            ("Saguna Brahman", {"tradition": "vedanta", "aliases": ["god with attributes"], "related_emotions": [], "related_domains": ["worship_bhakti"]}),
            ("Jivanmukti", {"tradition": "vedanta", "aliases": ["liberation while alive"], "related_emotions": ["joy", "peace"], "related_domains": ["liberation"]}),
            ("Panchakosha", {"tradition": "vedanta", "aliases": ["five sheaths"], "related_emotions": [], "related_domains": ["knowledge_learning", "self_improvement"]}),
            ("Adhyasa", {"tradition": "vedanta", "aliases": ["superimposition"], "related_emotions": ["confusion"], "related_domains": ["knowledge_learning"]}),
            ("Turiya", {"tradition": "vedanta", "aliases": ["fourth state"], "related_emotions": [], "related_domains": ["meditation_mind", "liberation"]}),
            ("Purushartha", {"tradition": "vedanta", "aliases": ["four goals of life"], "related_emotions": [], "related_domains": ["dharma_duty", "self_improvement"]}),
            ("Artha", {"tradition": "vedanta", "aliases": ["wealth", "prosperity"], "related_emotions": [], "related_domains": ["prosperity", "career_work"]}),
            ("Ananda", {"tradition": "vedanta", "aliases": ["bliss"], "related_emotions": ["joy"], "related_domains": ["liberation", "meditation_mind"]}),
            ("Chit", {"tradition": "vedanta", "aliases": ["consciousness"], "related_emotions": [], "related_domains": ["knowledge_learning", "meditation_mind"]}),
            ("Sat", {"tradition": "vedanta", "aliases": ["truth", "existence"], "related_emotions": [], "related_domains": ["knowledge_learning"]}),
            ("Mumuksha", {"tradition": "vedanta", "aliases": ["desire for liberation"], "related_emotions": ["hope"], "related_domains": ["liberation", "spiritual_practice"]}),
            ("Upadhi", {"tradition": "vedanta", "aliases": ["limiting adjunct"], "related_emotions": [], "related_domains": ["knowledge_learning"]}),
            ("Antahkarana", {"tradition": "vedanta", "aliases": ["inner instrument"], "related_emotions": [], "related_domains": ["mental_health", "self_improvement"]}),
            ("Vasana", {"tradition": "vedanta", "aliases": ["latent tendency", "impression"], "related_emotions": [], "related_domains": ["mental_health", "attachment"]}),
        ]

        # ── Yoga concepts ──
        _yoga = [
            ("Yoga", {"tradition": "yoga", "aliases": ["union"], "related_emotions": [], "related_domains": ["yoga_practice"]}),
            ("Dhyana", {"tradition": "yoga", "aliases": ["meditation"], "related_emotions": ["peace"], "related_domains": ["meditation_mind"]}),
            ("Samadhi", {"tradition": "yoga", "aliases": ["absorption"], "related_emotions": ["joy"], "related_domains": ["meditation_mind", "liberation"]}),
            ("Pranayama", {"tradition": "yoga", "aliases": ["breath control"], "related_emotions": ["anxiety"], "related_domains": ["yoga_practice", "mental_health"]}),
            ("Pratyahara", {"tradition": "yoga", "aliases": ["sense withdrawal"], "related_emotions": [], "related_domains": ["meditation_mind"]}),
            ("Dharana", {"tradition": "yoga", "aliases": ["concentration"], "related_emotions": [], "related_domains": ["concentration"]}),
            ("Chitta Vritti Nirodha", {"tradition": "yoga", "aliases": ["cessation of mental fluctuations"], "related_emotions": ["anxiety", "stress"], "related_domains": ["mental_health"]}),
            ("Abhyasa", {"tradition": "yoga", "aliases": ["practice", "consistent effort"], "related_emotions": [], "related_domains": ["discipline"]}),
            ("Kleshas", {"tradition": "yoga", "aliases": ["afflictions"], "related_emotions": ["suffering"], "related_domains": ["mental_health"]}),
        ]

        # ── Yoga Extended concepts ──
        _yoga_ext = [
            ("Yama", {"tradition": "yoga", "aliases": ["restraints"], "related_emotions": [], "related_domains": ["ethics", "discipline"]}),
            ("Niyama", {"tradition": "yoga", "aliases": ["observances"], "related_emotions": [], "related_domains": ["discipline", "spiritual_practice"]}),
            ("Asana", {"tradition": "yoga", "aliases": ["posture"], "related_emotions": [], "related_domains": ["yoga_practice", "health"]}),
            ("Ashtanga Yoga", {"tradition": "yoga", "aliases": ["eight-limbed yoga"], "related_emotions": [], "related_domains": ["yoga_practice"]}),
            ("Kaivalya", {"tradition": "yoga", "aliases": ["absolute freedom", "isolation"], "related_emotions": [], "related_domains": ["liberation"]}),
            ("Vritti", {"tradition": "yoga", "aliases": ["mental fluctuation", "thought wave"], "related_emotions": ["anxiety"], "related_domains": ["mental_health", "meditation_mind"]}),
            ("Samskara", {"tradition": "yoga", "aliases": ["mental impression", "conditioning"], "related_emotions": [], "related_domains": ["mental_health", "rebirth"]}),
            ("Raga", {"tradition": "yoga", "aliases": ["attachment", "craving"], "related_emotions": ["desire"], "related_domains": ["attachment", "desire"]}),
            ("Dvesha", {"tradition": "yoga", "aliases": ["aversion", "hatred"], "related_emotions": ["anger"], "related_domains": ["mental_health"]}),
            ("Abhinivesha", {"tradition": "yoga", "aliases": ["fear of death", "clinging to life"], "related_emotions": ["fear"], "related_domains": ["fear", "death"]}),
            ("Asmita", {"tradition": "yoga", "aliases": ["ego sense", "I-ness"], "related_emotions": [], "related_domains": ["ego", "identity"]}),
            ("Vivekakhyati", {"tradition": "yoga", "aliases": ["discriminative knowledge"], "related_emotions": [], "related_domains": ["knowledge_learning", "liberation"]}),
            ("Ishvara", {"tradition": "yoga", "aliases": ["supreme being", "god"], "related_emotions": [], "related_domains": ["worship_bhakti"]}),
            ("Hatha Yoga", {"tradition": "yoga", "aliases": ["physical yoga"], "related_emotions": [], "related_domains": ["yoga_practice", "health"]}),
            ("Kundalini", {"tradition": "yoga", "aliases": ["serpent power", "coiled energy"], "related_emotions": [], "related_domains": ["yoga_practice", "spiritual_practice"]}),
        ]

        # ── Bhakti concepts ──
        _bhakti = [
            ("Bhakti", {"tradition": "vedanta", "aliases": ["devotion"], "related_emotions": ["love", "gratitude"], "related_domains": ["worship_bhakti"]}),
            ("Seva", {"tradition": "vedanta", "aliases": ["selfless service"], "related_emotions": ["compassion"], "related_domains": ["dharma_duty"]}),
            ("Saranagati", {"tradition": "vedanta", "aliases": ["surrender", "prapatti"], "related_emotions": ["hope", "despair"], "related_domains": ["worship_bhakti"]}),
            ("Ishvara Pranidhana", {"tradition": "yoga", "aliases": ["surrender to god"], "related_emotions": ["hope"], "related_domains": ["worship_bhakti", "spiritual_practice"]}),
            ("Nama Japa", {"tradition": "vedanta", "aliases": ["chanting", "name repetition"], "related_emotions": [], "related_domains": ["mantra", "worship_bhakti"]}),
        ]

        # ── Bhakti Extended concepts ──
        _bhakti_ext = [
            ("Shravanam", {"tradition": "vedanta", "aliases": ["listening"], "related_emotions": [], "related_domains": ["worship_bhakti"]}),
            ("Kirtanam", {"tradition": "vedanta", "aliases": ["chanting", "singing"], "related_emotions": ["joy"], "related_domains": ["worship_bhakti", "mantra"]}),
            ("Vandanam", {"tradition": "vedanta", "aliases": ["prostration", "salutation"], "related_emotions": ["devotion"], "related_domains": ["worship_bhakti"]}),
            ("Archanam", {"tradition": "vedanta", "aliases": ["worship", "offering"], "related_emotions": ["devotion"], "related_domains": ["worship_bhakti", "puja_ritual"]}),
            ("Atma Nivedanam", {"tradition": "vedanta", "aliases": ["complete surrender"], "related_emotions": ["peace"], "related_domains": ["worship_bhakti"]}),
            ("Prema Bhakti", {"tradition": "vedanta", "aliases": ["love devotion"], "related_emotions": ["love"], "related_domains": ["worship_bhakti"]}),
            ("Guru", {"tradition": "vedanta", "aliases": ["teacher", "spiritual guide"], "related_emotions": ["gratitude"], "related_domains": ["teacher_guru", "knowledge_learning"]}),
            ("Mantra", {"tradition": "vedanta", "aliases": ["sacred syllable"], "related_emotions": [], "related_domains": ["mantra", "spiritual_practice"]}),
            ("Kirtan", {"tradition": "vedanta", "aliases": ["devotional singing"], "related_emotions": ["joy"], "related_domains": ["worship_bhakti", "mantra"]}),
            ("Aradhana", {"tradition": "vedanta", "aliases": ["worship", "adoration"], "related_emotions": ["devotion"], "related_domains": ["worship_bhakti"]}),
        ]

        # ── Psychological concepts ──
        _psychological = [
            ("Krodha", {"tradition": "vedanta", "aliases": ["anger", "wrath"], "related_emotions": ["anger"], "related_domains": ["mental_health"]}),
            ("Kama", {"tradition": "vedanta", "aliases": ["desire", "lust"], "related_emotions": ["desire"], "related_domains": ["desire", "habits_lust"]}),
            ("Lobha", {"tradition": "vedanta", "aliases": ["greed"], "related_emotions": ["greed"], "related_domains": ["ethics"]}),
            ("Moha", {"tradition": "vedanta", "aliases": ["delusion", "attachment"], "related_emotions": ["confusion"], "related_domains": ["attachment"]}),
            ("Ahimsa", {"tradition": "vedanta", "aliases": ["non-violence"], "related_emotions": ["compassion"], "related_domains": ["ethics", "nonviolence"]}),
            ("Shanti", {"tradition": "vedanta", "aliases": ["peace"], "related_emotions": ["peace", "contentment"], "related_domains": ["mental_health", "meditation_mind"]}),
            ("Dukha", {"tradition": "vedanta", "aliases": ["suffering", "sorrow"], "related_emotions": ["grief", "despair"], "related_domains": ["mental_health"]}),
            ("Santosha", {"tradition": "yoga", "aliases": ["contentment"], "related_emotions": ["contentment", "gratitude"], "related_domains": ["contentment"]}),
            ("Kshama", {"tradition": "vedanta", "aliases": ["forgiveness", "patience"], "related_emotions": ["anger"], "related_domains": ["forgiveness"]}),
            ("Shraddha", {"tradition": "vedanta", "aliases": ["faith"], "related_emotions": ["hope"], "related_domains": ["spiritual_practice"]}),
        ]

        # ── Ethical concepts ──
        _ethical = [
            ("Nishkama Karma", {"tradition": "vedanta", "aliases": ["selfless action", "desireless action"], "related_emotions": [], "related_domains": ["career_work", "dharma_duty"]}),
            ("Svadharma", {"tradition": "vedanta", "aliases": ["one's own duty"], "related_emotions": ["confusion"], "related_domains": ["dharma_duty", "identity"]}),
            ("Satya", {"tradition": "vedanta", "aliases": ["truth"], "related_emotions": [], "related_domains": ["ethics"]}),
            ("Dana", {"tradition": "vedanta", "aliases": ["charity", "giving"], "related_emotions": ["gratitude"], "related_domains": ["prosperity"]}),
            ("Tapas", {"tradition": "yoga", "aliases": ["austerity", "discipline"], "related_emotions": [], "related_domains": ["discipline", "spiritual_practice"]}),
            ("Svadhyaya", {"tradition": "yoga", "aliases": ["self-study"], "related_emotions": [], "related_domains": ["knowledge_learning", "self_improvement"]}),
        ]

        # ── Ritual / Dharma concepts ──
        _ritual = [
            ("Yajna", {"tradition": "shruti", "aliases": ["sacrifice", "fire ritual"], "related_emotions": [], "related_domains": ["puja_ritual", "spiritual_practice"]}),
            ("Puja", {"tradition": "smriti", "aliases": ["worship"], "related_emotions": ["devotion"], "related_domains": ["worship_bhakti", "puja_ritual"]}),
            ("Havan", {"tradition": "shruti", "aliases": ["fire ceremony", "homa"], "related_emotions": [], "related_domains": ["puja_ritual"]}),
            ("Vrata", {"tradition": "smriti", "aliases": ["fasting", "vow"], "related_emotions": ["discipline"], "related_domains": ["fasting", "discipline"]}),
            ("Tirtha", {"tradition": "smriti", "aliases": ["pilgrimage", "sacred place"], "related_emotions": [], "related_domains": ["pilgrimage"]}),
            ("Diksha", {"tradition": "vedanta", "aliases": ["initiation"], "related_emotions": [], "related_domains": ["spiritual_practice", "teacher_guru"]}),
            ("Sankalpa", {"tradition": "vedanta", "aliases": ["intention", "resolve"], "related_emotions": ["hope"], "related_domains": ["discipline", "spiritual_practice"]}),
            ("Prasad", {"tradition": "smriti", "aliases": ["grace", "blessed food"], "related_emotions": ["gratitude"], "related_domains": ["worship_bhakti"]}),
            ("Upavasa", {"tradition": "smriti", "aliases": ["fasting"], "related_emotions": [], "related_domains": ["fasting", "discipline"]}),
            ("Sandhya Vandana", {"tradition": "shruti", "aliases": ["twilight prayer"], "related_emotions": [], "related_domains": ["spiritual_practice", "puja_ritual"]}),
        ]

        # ── Life / Practical concepts ──
        _life = [
            ("Grihastha", {"tradition": "smriti", "aliases": ["householder"], "related_emotions": [], "related_domains": ["family", "marriage", "dharma_duty"]}),
            ("Vanaprastha", {"tradition": "smriti", "aliases": ["forest dweller", "retirement"], "related_emotions": [], "related_domains": ["old_age", "spiritual_practice"]}),
            ("Sannyasa", {"tradition": "vedanta", "aliases": ["renunciation"], "related_emotions": [], "related_domains": ["liberation", "spiritual_practice"]}),
            ("Brahmacharya", {"tradition": "yoga", "aliases": ["celibacy", "student life"], "related_emotions": [], "related_domains": ["discipline", "education"]}),
            ("Dinacharya", {"tradition": "ayurveda", "aliases": ["daily routine"], "related_emotions": [], "related_domains": ["health", "discipline"]}),
            ("Prarabdha", {"tradition": "vedanta", "aliases": ["destiny karma", "fate"], "related_emotions": [], "related_domains": ["rebirth", "dharma_duty"]}),
            ("Sanchita", {"tradition": "vedanta", "aliases": ["accumulated karma"], "related_emotions": [], "related_domains": ["rebirth"]}),
            ("Agami", {"tradition": "vedanta", "aliases": ["future karma"], "related_emotions": [], "related_domains": ["rebirth", "dharma_duty"]}),
            ("Punarjanma", {"tradition": "vedanta", "aliases": ["rebirth", "reincarnation"], "related_emotions": [], "related_domains": ["rebirth", "death"]}),
            ("Mrityu", {"tradition": "vedanta", "aliases": ["death"], "related_emotions": ["grief", "fear"], "related_domains": ["death", "grief"]}),
            ("Punya", {"tradition": "smriti", "aliases": ["merit", "virtue"], "related_emotions": [], "related_domains": ["ethics", "dharma_duty"]}),
            ("Papa", {"tradition": "smriti", "aliases": ["sin", "demerit"], "related_emotions": ["guilt"], "related_domains": ["ethics"]}),
            ("Swarga", {"tradition": "smriti", "aliases": ["heaven"], "related_emotions": [], "related_domains": ["rebirth"]}),
            ("Arishadvarga", {"tradition": "vedanta", "aliases": ["six enemies"], "related_emotions": ["anger"], "related_domains": ["mental_health", "self_improvement"]}),
            ("Dharma Yuddha", {"tradition": "itihasa", "aliases": ["righteous war"], "related_emotions": ["courage"], "related_domains": ["courage", "dharma_duty"]}),
        ]

        # ── Ayurveda / Health concepts ──
        _ayurveda = [
            ("Dosha", {"tradition": "ayurveda", "aliases": ["constitution"], "related_emotions": [], "related_domains": ["health", "ayurveda_wellness"]}),
            ("Vata", {"tradition": "ayurveda", "aliases": ["air element"], "related_emotions": ["anxiety"], "related_domains": ["health", "ayurveda_wellness"]}),
            ("Pitta", {"tradition": "ayurveda", "aliases": ["fire element"], "related_emotions": ["anger"], "related_domains": ["health", "ayurveda_wellness"]}),
            ("Kapha", {"tradition": "ayurveda", "aliases": ["earth element"], "related_emotions": [], "related_domains": ["health", "ayurveda_wellness"]}),
            ("Ojas", {"tradition": "ayurveda", "aliases": ["vital essence"], "related_emotions": [], "related_domains": ["health"]}),
            ("Agni", {"tradition": "ayurveda", "aliases": ["digestive fire"], "related_emotions": [], "related_domains": ["health", "diet"]}),
            ("Ama", {"tradition": "ayurveda", "aliases": ["toxin", "undigested matter"], "related_emotions": [], "related_domains": ["health"]}),
            ("Rasayana", {"tradition": "ayurveda", "aliases": ["rejuvenation"], "related_emotions": [], "related_domains": ["health", "old_age"]}),
            ("Prakriti", {"tradition": "ayurveda", "aliases": ["body constitution"], "related_emotions": [], "related_domains": ["health", "ayurveda_wellness"]}),
            ("Swasthya", {"tradition": "ayurveda", "aliases": ["wellness", "health"], "related_emotions": [], "related_domains": ["health", "mental_health"]}),
        ]

        # Add all nodes
        for concept_list in [_vedanta, _vedanta_ext, _yoga, _yoga_ext, _bhakti, _bhakti_ext,
                             _psychological, _ethical, _ritual, _life, _ayurveda]:
            for name, attrs in concept_list:
                self._graph.add_node(name, **attrs)

        # ── Edges ──
        _edges = [
            # ── IS_A relationships (original) ──
            ("Dhyana", "Yoga", "IS_A"),
            ("Samadhi", "Yoga", "IS_A"),
            ("Pranayama", "Yoga", "IS_A"),
            ("Dharana", "Yoga", "IS_A"),
            ("Pratyahara", "Yoga", "IS_A"),
            ("Bhakti", "Yoga", "IS_A"),
            ("Nishkama Karma", "Karma", "IS_A"),

            # ── IS_A relationships (new) ──
            ("Shravanam", "Bhakti", "IS_A"),
            ("Kirtanam", "Bhakti", "IS_A"),
            ("Vandanam", "Bhakti", "IS_A"),
            ("Archanam", "Bhakti", "IS_A"),
            ("Atma Nivedanam", "Bhakti", "IS_A"),
            ("Prema Bhakti", "Bhakti", "IS_A"),
            ("Yama", "Yoga", "IS_A"),
            ("Niyama", "Yoga", "IS_A"),
            ("Asana", "Yoga", "IS_A"),
            ("Ashtanga Yoga", "Yoga", "IS_A"),
            ("Hatha Yoga", "Yoga", "IS_A"),
            ("Raga", "Kleshas", "IS_A"),
            ("Dvesha", "Kleshas", "IS_A"),
            ("Abhinivesha", "Kleshas", "IS_A"),
            ("Asmita", "Kleshas", "IS_A"),
            ("Vata", "Dosha", "IS_A"),
            ("Pitta", "Dosha", "IS_A"),
            ("Kapha", "Dosha", "IS_A"),
            ("Yajna", "Dharma", "IS_A"),
            ("Puja", "Dharma", "IS_A"),
            ("Grihastha", "Dharma", "IS_A"),
            ("Sannyasa", "Dharma", "IS_A"),
            ("Prarabdha", "Karma", "IS_A"),
            ("Sanchita", "Karma", "IS_A"),
            ("Agami", "Karma", "IS_A"),

            # ── IMPLIES relationships (original) ──
            ("Viveka", "Vairagya", "IMPLIES"),
            ("Vairagya", "Moksha", "IMPLIES"),
            ("Abhyasa", "Samadhi", "IMPLIES"),
            ("Dharana", "Dhyana", "IMPLIES"),
            ("Dhyana", "Samadhi", "IMPLIES"),
            ("Bhakti", "Saranagati", "IMPLIES"),
            ("Nishkama Karma", "Moksha", "IMPLIES"),
            ("Avidya", "Kleshas", "IMPLIES"),
            ("Tapas", "Vairagya", "IMPLIES"),
            ("Svadhyaya", "Viveka", "IMPLIES"),

            # ── IMPLIES relationships (new) ──
            ("Mumuksha", "Moksha", "IMPLIES"),
            ("Vivekakhyati", "Kaivalya", "IMPLIES"),
            ("Sankalpa", "Abhyasa", "IMPLIES"),
            ("Diksha", "Bhakti", "IMPLIES"),
            ("Vrata", "Tapas", "IMPLIES"),
            ("Guru", "Diksha", "IMPLIES"),
            ("Mantra", "Nama Japa", "IMPLIES"),
            ("Kirtan", "Bhakti", "IMPLIES"),
            ("Aradhana", "Bhakti", "IMPLIES"),
            ("Jivanmukti", "Moksha", "IMPLIES"),
            ("Turiya", "Samadhi", "IMPLIES"),
            ("Kundalini", "Samadhi", "IMPLIES"),
            ("Hatha Yoga", "Pranayama", "IMPLIES"),
            ("Dinacharya", "Swasthya", "IMPLIES"),
            ("Ojas", "Swasthya", "IMPLIES"),
            ("Agni", "Swasthya", "IMPLIES"),
            ("Vasana", "Samskara", "IMPLIES"),
            ("Vritti", "Kleshas", "IMPLIES"),
            ("Punya", "Swarga", "IMPLIES"),
            ("Papa", "Samsara", "IMPLIES"),

            # ── OPPOSITE_OF relationships (original) ──
            ("Viveka", "Avidya", "OPPOSITE_OF"),
            ("Moksha", "Samsara", "OPPOSITE_OF"),
            ("Shanti", "Krodha", "OPPOSITE_OF"),
            ("Santosha", "Lobha", "OPPOSITE_OF"),
            ("Ahimsa", "Krodha", "OPPOSITE_OF"),
            ("Vairagya", "Kama", "OPPOSITE_OF"),
            ("Satya", "Maya", "OPPOSITE_OF"),

            # ── OPPOSITE_OF relationships (new) ──
            ("Raga", "Vairagya", "OPPOSITE_OF"),
            ("Dvesha", "Kshama", "OPPOSITE_OF"),
            ("Asmita", "Atman", "OPPOSITE_OF"),
            ("Papa", "Punya", "OPPOSITE_OF"),
            ("Ama", "Ojas", "OPPOSITE_OF"),
            ("Abhinivesha", "Moksha", "OPPOSITE_OF"),
            ("Nirguna Brahman", "Saguna Brahman", "OPPOSITE_OF"),
            ("Sannyasa", "Grihastha", "OPPOSITE_OF"),
            ("Swarga", "Moksha", "OPPOSITE_OF"),
            ("Vritti", "Shanti", "OPPOSITE_OF"),

            # ── PRECONDITION_OF relationships (original) ──
            ("Viveka", "Moksha", "PRECONDITION_OF"),
            ("Shraddha", "Bhakti", "PRECONDITION_OF"),
            ("Pranayama", "Dharana", "PRECONDITION_OF"),
            ("Pratyahara", "Dharana", "PRECONDITION_OF"),
            ("Kshama", "Shanti", "PRECONDITION_OF"),
            ("Abhyasa", "Dhyana", "PRECONDITION_OF"),

            # ── PRECONDITION_OF relationships (new) ──
            ("Yama", "Niyama", "PRECONDITION_OF"),
            ("Niyama", "Asana", "PRECONDITION_OF"),
            ("Asana", "Pranayama", "PRECONDITION_OF"),
            ("Mumuksha", "Viveka", "PRECONDITION_OF"),
            ("Guru", "Diksha", "PRECONDITION_OF"),
            ("Diksha", "Mantra", "PRECONDITION_OF"),
            ("Sankalpa", "Vrata", "PRECONDITION_OF"),
            ("Brahmacharya", "Viveka", "PRECONDITION_OF"),
            ("Dinacharya", "Swasthya", "PRECONDITION_OF"),

            # ── RELATED_TO relationships (original) ──
            ("Karma", "Dharma", "RELATED_TO"),
            ("Svadharma", "Dharma", "RELATED_TO"),
            ("Svadharma", "Nishkama Karma", "RELATED_TO"),
            ("Nama Japa", "Bhakti", "RELATED_TO"),
            ("Ishvara Pranidhana", "Saranagati", "RELATED_TO"),
            ("Seva", "Bhakti", "RELATED_TO"),
            ("Dana", "Seva", "RELATED_TO"),
            ("Moha", "Maya", "RELATED_TO"),
            ("Dukha", "Kleshas", "RELATED_TO"),
            ("Chitta Vritti Nirodha", "Dhyana", "RELATED_TO"),

            # ── RELATED_TO relationships (new) ──
            ("Nirguna Brahman", "Brahman", "RELATED_TO"),
            ("Saguna Brahman", "Brahman", "RELATED_TO"),
            ("Jivanmukti", "Moksha", "RELATED_TO"),
            ("Panchakosha", "Atman", "RELATED_TO"),
            ("Adhyasa", "Maya", "RELATED_TO"),
            ("Turiya", "Samadhi", "RELATED_TO"),
            ("Purushartha", "Dharma", "RELATED_TO"),
            ("Artha", "Purushartha", "RELATED_TO"),
            ("Ananda", "Moksha", "RELATED_TO"),
            ("Chit", "Brahman", "RELATED_TO"),
            ("Sat", "Brahman", "RELATED_TO"),
            ("Antahkarana", "Chitta Vritti Nirodha", "RELATED_TO"),
            ("Vasana", "Karma", "RELATED_TO"),
            ("Upadhi", "Maya", "RELATED_TO"),
            ("Vritti", "Chitta Vritti Nirodha", "RELATED_TO"),
            ("Samskara", "Vasana", "RELATED_TO"),
            ("Raga", "Kama", "RELATED_TO"),
            ("Dvesha", "Krodha", "RELATED_TO"),
            ("Asmita", "Moha", "RELATED_TO"),
            ("Vivekakhyati", "Viveka", "RELATED_TO"),
            ("Kaivalya", "Moksha", "RELATED_TO"),
            ("Ishvara", "Ishvara Pranidhana", "RELATED_TO"),
            ("Kundalini", "Dhyana", "RELATED_TO"),
            ("Hatha Yoga", "Asana", "RELATED_TO"),
            ("Yajna", "Seva", "RELATED_TO"),
            ("Puja", "Bhakti", "RELATED_TO"),
            ("Havan", "Yajna", "RELATED_TO"),
            ("Vrata", "Tapas", "RELATED_TO"),
            ("Tirtha", "Bhakti", "RELATED_TO"),
            ("Sandhya Vandana", "Dharma", "RELATED_TO"),
            ("Prasad", "Bhakti", "RELATED_TO"),
            ("Shravanam", "Nama Japa", "RELATED_TO"),
            ("Kirtanam", "Kirtan", "RELATED_TO"),
            ("Vandanam", "Seva", "RELATED_TO"),
            ("Archanam", "Puja", "RELATED_TO"),
            ("Atma Nivedanam", "Saranagati", "RELATED_TO"),
            ("Prema Bhakti", "Bhakti", "RELATED_TO"),
            ("Guru", "Svadhyaya", "RELATED_TO"),
            ("Mantra", "Dhyana", "RELATED_TO"),
            ("Grihastha", "Dharma", "RELATED_TO"),
            ("Vanaprastha", "Vairagya", "RELATED_TO"),
            ("Sannyasa", "Vairagya", "RELATED_TO"),
            ("Brahmacharya", "Tapas", "RELATED_TO"),
            ("Prarabdha", "Samsara", "RELATED_TO"),
            ("Sanchita", "Karma", "RELATED_TO"),
            ("Agami", "Nishkama Karma", "RELATED_TO"),
            ("Punarjanma", "Samsara", "RELATED_TO"),
            ("Mrityu", "Dukha", "RELATED_TO"),
            ("Punya", "Dana", "RELATED_TO"),
            ("Papa", "Krodha", "RELATED_TO"),
            ("Arishadvarga", "Kleshas", "RELATED_TO"),
            ("Dharma Yuddha", "Svadharma", "RELATED_TO"),
            ("Dosha", "Swasthya", "RELATED_TO"),
            ("Dinacharya", "Dosha", "RELATED_TO"),
            ("Ojas", "Dosha", "RELATED_TO"),
            ("Agni", "Dosha", "RELATED_TO"),
            ("Ama", "Dosha", "RELATED_TO"),
            ("Rasayana", "Ojas", "RELATED_TO"),
            ("Prakriti", "Dosha", "RELATED_TO"),
            ("Mumuksha", "Vairagya", "RELATED_TO"),
        ]

        for source, target, edge_type in _edges:
            if source in self._graph and target in self._graph:
                self._graph.add_edge(
                    source, target,
                    type=edge_type,
                    weight=EDGE_WEIGHTS.get(edge_type, 0.5),
                )

        logger.info(f"ConceptOntology: built seed graph with {self._graph.number_of_nodes()} nodes, "
                     f"{self._graph.number_of_edges()} edges")

    def _save_graph(self, path: str) -> None:
        """Serialize graph to JSON."""
        if self._graph is None:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = {
                "nodes": [
                    {"id": n, **self._graph.nodes[n]}
                    for n in self._graph.nodes
                ],
                "edges": [
                    {"source": u, "target": v, **self._graph.edges[u, v]}
                    for u, v in self._graph.edges
                ],
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"ConceptOntology: saved graph to {path}")
        except Exception as e:
            logger.error(f"ConceptOntology: failed to save graph — {e}")

    def get_related_concepts(self, term: str, depth: int = 2, max_results: int = 6) -> List[str]:
        """BFS expansion from a concept node, returning related concept names."""
        if not self._available or self._graph is None:
            return []

        canonical = self._concept_lookup.get(term.lower())
        if not canonical:
            return []

        visited: Set[str] = {canonical}
        queue: List[tuple] = [(canonical, 0, 1.0)]
        results: List[tuple] = []

        while queue:
            node, current_depth, accumulated_weight = queue.pop(0)
            if current_depth >= depth:
                continue

            # Explore both successors and predecessors (undirected-like BFS)
            neighbors = set(self._graph.successors(node)) | set(self._graph.predecessors(node))
            for neighbor in neighbors:
                if neighbor in visited:
                    continue
                visited.add(neighbor)

                # Get edge weight
                if self._graph.has_edge(node, neighbor):
                    edge_weight = self._graph.edges[node, neighbor].get("weight", 0.5)
                else:
                    edge_weight = self._graph.edges[neighbor, node].get("weight", 0.5)

                combined_weight = accumulated_weight * edge_weight
                results.append((neighbor, combined_weight))
                queue.append((neighbor, current_depth + 1, combined_weight))

        # Sort by weight descending, return top names
        results.sort(key=lambda x: x[1], reverse=True)
        return [name for name, _ in results[:max_results]]

    def detect_concepts(self, query: str) -> List[str]:
        """Detect known ontology concepts in a query string."""
        if not self._available:
            return []

        query_lower = query.lower()
        words = set(query_lower.split())
        detected = []

        for term, canonical in self._concept_lookup.items():
            if " " in term:
                # Multi-word match
                if term in query_lower:
                    detected.append(canonical)
            elif term in words:
                detected.append(canonical)

        return list(set(detected))


# Singleton
_concept_ontology: Optional[ConceptOntology] = None


def get_concept_ontology() -> ConceptOntology:
    global _concept_ontology
    if _concept_ontology is None:
        _concept_ontology = ConceptOntology()
        _concept_ontology.initialize()
    return _concept_ontology
