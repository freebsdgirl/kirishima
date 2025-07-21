#!/usr/bin/env python3
"""
Memory deduplication analysis and management script for Kirishima Ledger service.

This script provides tools to analyze memory duplication patterns and execute
the enhanced deduplication process. It connects directly to the ledger service
API to perform various deduplication operations including semantic clustering.

Usage:
    python analyze_dedup.py [command] [options]
    
Commands:
    analyze           - Analyze potential for deduplication without making changes
    deduplicate       - Run the enhanced deduplication process
    dedup-semantic    - Run semantic deduplication using sentence-transformers
    scan-semantic     - Run semantic message scanning using clustering
    preview-semantic  - Preview semantic scan without processing
    dedup-topics      - Run semantic topic deduplication
    preview-topics    - Preview topic deduplication without processing
    dedup-topic-based - Run topic-based memory deduplication (NEW!)
    preview-topic-based - Preview topic-based deduplication (NEW!)
    consolidate-topics - Analyze all topics for consolidation (NEW!)
    stats             - Show basic statistics about memories and topics
    similar           - Find memories with similar keywords
    
Examples:
    python analyze_dedup.py analyze
    python analyze_dedup.py deduplicate
    python analyze_dedup.py dedup-semantic --similarity 0.8
    python analyze_dedup.py scan-semantic --clusters 3
    python analyze_dedup.py dedup-topics --similarity 0.75
    python analyze_dedup.py preview-topic-based --similarity 0.8 --keywords 2
    python analyze_dedup.py dedup-topic-based --similarity 0.8 --keywords 3
    python analyze_dedup.py consolidate-topics
    python analyze_dedup.py similar --keywords 2
"""

import asyncio
import argparse
import json
import sys
from typing import List, Dict
import httpx

# Configuration
LEDGER_HOST = "localhost"
LEDGER_PORT = 4203
BASE_URL = f"http://{LEDGER_HOST}:{LEDGER_PORT}"

async def analyze_dedup_potential():
    """Analyze potential for deduplication without making changes"""
    print("🔍 Analyzing memory deduplication potential...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/memories/_dedup_analyze")
            response.raise_for_status()
            data = response.json()
            
            print("\n📊 DEDUPLICATION ANALYSIS RESULTS")
            print("=" * 50)
            
            stats = data["statistics"]
            print(f"Total Topics: {stats['total_topics']}")
            print(f"Total Memories: {stats['total_memories']}")
            
            print("\n🔗 Keyword Overlap Analysis:")
            overlaps = stats["keyword_overlaps"]
            print(f"  Memories with 2+ common keywords: {overlaps['2_keywords']}")
            print(f"  Memories with 3+ common keywords: {overlaps['3_keywords']}")
            print(f"  Memories with 4+ common keywords: {overlaps['4_keywords']}")
            
            print("\n📚 Top Topics by Memory Count:")
            for i, topic in enumerate(data["top_topics_by_memory_count"][:10], 1):
                print(f"  {i:2d}. {topic['name'][:60]:<60} ({topic['memory_count']} memories)")
            
            if data.get("sample_high_overlap_pairs"):
                print("\n🎯 Sample High-Overlap Memory Pairs:")
                for i, (mem1, mem2, overlap) in enumerate(data["sample_high_overlap_pairs"][:5], 1):
                    print(f"  {i}. {mem1} ↔ {mem2} ({overlap} common keywords)")
            
            # Calculate deduplication potential
            total_potential = overlaps['2_keywords']
            if total_potential > 0:
                print(f"\n💡 DEDUPLICATION POTENTIAL")
                print(f"   Estimated {total_potential} memory pairs could be deduplicated")
                print(f"   This could reduce memory count by up to {total_potential // 2} memories")
                print(f"   Recommended to start with 3+ keyword overlaps ({overlaps['3_keywords']} pairs)")
            else:
                print("\n✅ No obvious duplicates found based on keyword overlap")
                
        except httpx.HTTPError as e:
            print(f"❌ Error analyzing deduplication potential: {e}")
            return False
    
    return True

async def run_enhanced_deduplication():
    """Run the enhanced deduplication process"""
    print("🚀 Starting enhanced memory deduplication...")
    
    # First, show preview
    print("📋 Getting preview of what will be processed...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/memories/_dedup_preview")
            response.raise_for_status()
            preview = response.json()
            
            if preview["status"] == "no_candidates":
                print("❌ No memory candidates found for deduplication")
                return False
            
            summary = preview["summary"]
            print(f"\n📊 DEDUPLICATION PREVIEW:")
            print(f"   Total keyword overlap pairs: {summary['total_keyword_overlap_pairs']}")
            print(f"   Total groups found: {summary['total_groups_found']}")
            print(f"   Groups to be processed: {summary['groups_that_would_be_processed']}")
            print(f"   Estimated LLM calls: {summary['estimated_llm_calls']}")
            print(f"   Total memories in groups: {summary['total_memories_in_filtered_groups']}")
            
            # Show sample groups
            if preview.get("groups_preview"):
                print(f"\n🔍 SAMPLE GROUPS TO BE PROCESSED:")
                for group in preview["groups_preview"][:3]:
                    print(f"   Group {group['group_index']}: {group['memory_count']} memories")
                    for mem in group["memories"][:2]:  # Show first 2 memories per group
                        print(f"     • {mem['memory_preview']}")
                        print(f"       Keywords: {', '.join(mem['keywords'][:3])}")
                    if len(group["memories"]) > 2:
                        print(f"     ... and {len(group['memories']) - 2} more")
                    print()
            
        except Exception as e:
            print(f"❌ Error getting preview: {e}")
            return False
    
    # Ask for confirmation
    response = input(f"Continue with deduplication of {summary['groups_that_would_be_processed']} groups? (y/N): ")
    if response.lower() != 'y':
        print("❌ Deduplication cancelled")
        return False
    
    async with httpx.AsyncClient(timeout=300) as client:  # 5 minute timeout
        try:
            print("⏳ Running deduplication process (this may take a few minutes)...")
            response = await client.post(f"{BASE_URL}/memories/_dedup_v2")
            response.raise_for_status()
            data = response.json()
            
            print("\n🎉 DEDUPLICATION RESULTS")
            print("=" * 50)
            
            # Keyword-based results
            keyword_results = data.get("keyword_based_dedup", {})
            print(f"🔤 Keyword-based deduplication:")
            print(f"   Processed groups: {keyword_results.get('processed_groups', 0)}")
            
            total_updates = 0
            total_deletions = 0
            
            for result in keyword_results.get("results", []):
                updates = result.get("update_count", 0)
                deletions = result.get("delete_count", 0)
                total_updates += updates
                total_deletions += deletions
                if updates > 0 or deletions > 0:
                    print(f"     Group: {updates} updates, {deletions} deletions")
            
            # Topic-based results
            topic_results = data.get("topic_based_dedup", {})
            print(f"\n📋 Topic-based deduplication:")
            print(f"   Processed groups: {topic_results.get('processed_groups', 0)}")
            
            for result in topic_results.get("results", []):
                dedup_result = result.get("dedup_result", {})
                updates = dedup_result.get("update_count", 0)
                deletions = dedup_result.get("delete_count", 0)
                total_updates += updates
                total_deletions += deletions
                if updates > 0 or deletions > 0:
                    topic_group = result.get("topic_group", [])
                    print(f"     Topics {topic_group}: {updates} updates, {deletions} deletions")
            
            # Summary
            print(f"\n📈 SUMMARY:")
            print(f"   Total memory updates: {total_updates}")
            print(f"   Total memory deletions: {total_deletions}")
            print(f"   Net reduction: {total_deletions} memories")
            
            # Statistics
            stats = data.get("stats", {})
            print(f"\n📊 Processing Statistics:")
            print(f"   Keyword overlap pairs analyzed: {stats.get('keyword_overlap_pairs', 0)}")
            print(f"   Similar topic groups found: {stats.get('similar_topic_groups', 0)}")
            print(f"   Unique memories analyzed: {stats.get('total_unique_memories_analyzed', 0)}")
            
        except httpx.HTTPError as e:
            print(f"❌ Error running deduplication: {e}")
            return False
        except asyncio.TimeoutError:
            print("⏰ Deduplication process timed out - it may still be running")
            return False
    
    return True

async def show_basic_stats():
    """Show basic statistics about memories and topics"""
    print("📊 Memory and Topic Statistics")
    print("=" * 40)
    
    async with httpx.AsyncClient() as client:
        try:
            # Get memory count
            response = await client.get(f"{BASE_URL}/memories")
            response.raise_for_status()
            memories = response.json()
            print(f"Total Memories: {len(memories)}")
            
            # Get topic count
            response = await client.get(f"{BASE_URL}/topics")
            response.raise_for_status()
            topics = response.json()
            print(f"Total Topics: {len(topics)}")
            
            # Calculate averages
            if len(topics) > 0:
                print(f"Average memories per topic: {len(memories) / len(topics):.2f}")
            
        except httpx.HTTPError as e:
            print(f"❌ Error fetching statistics: {e}")
            return False
    
    return True

async def preview_deduplication(min_overlap: int = 3, max_groups: int = 20):
    """Preview what would be processed in deduplication"""
    print(f"🔍 Previewing deduplication with {min_overlap}+ keyword overlap...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/memories/_dedup_preview",
                params={
                    "min_keyword_overlap": min_overlap,
                    "max_groups_to_process": max_groups,
                    "max_memories_per_group": 10
                }
            )
            response.raise_for_status()
            preview = response.json()
            
            if preview["status"] == "no_candidates":
                print("❌ No memory candidates found for deduplication")
                return False
            
            print("\n📊 DEDUPLICATION PREVIEW")
            print("=" * 50)
            
            summary = preview["summary"]
            print(f"Total keyword overlap pairs found: {summary['total_keyword_overlap_pairs']}")
            print(f"Total memory groups found: {summary['total_groups_found']}")
            print(f"Groups that would be processed: {summary['groups_that_would_be_processed']}")
            print(f"Estimated LLM calls needed: {summary['estimated_llm_calls']}")
            print(f"Total memories in filtered groups: {summary['total_memories_in_filtered_groups']}")
            
            config = preview["filtering_config"]
            print(f"\n⚙️  FILTERING CONFIGURATION:")
            print(f"   Minimum keyword overlap: {config['min_keyword_overlap']}")
            print(f"   Max groups to process: {config['max_groups_to_process']}")
            print(f"   Max memories per group: {config['max_memories_per_group']}")
            
            # Show detailed groups
            if preview.get("groups_preview"):
                print(f"\n🔍 MEMORY GROUPS TO BE PROCESSED:")
                for group in preview["groups_preview"]:
                    print(f"\n   📁 Group {group['group_index']} ({group['memory_count']} memories):")
                    for i, mem in enumerate(group["memories"]):
                        print(f"      {i+1}. {mem['memory_preview']}")
                        if mem['keywords']:
                            print(f"         🏷️  Keywords: {', '.join(mem['keywords'])}")
                        if mem['category']:
                            print(f"         📂 Category: {mem['category']}")
                        print()
            
            print(f"💡 RECOMMENDATION:")
            if summary['estimated_llm_calls'] > 50:
                print(f"   ⚠️  {summary['estimated_llm_calls']} LLM calls is quite high!")
                print(f"   Consider increasing min_keyword_overlap to {min_overlap + 1} or reducing max_groups")
            elif summary['estimated_llm_calls'] == 0:
                print(f"   ℹ️  No groups to process with current settings")
                print(f"   Consider lowering min_keyword_overlap to {max(2, min_overlap - 1)}")
            else:
                print(f"   ✅ {summary['estimated_llm_calls']} LLM calls seems reasonable")
            
        except httpx.HTTPError as e:
            print(f"❌ Error getting preview: {e}")
            return False
    
    return True

async def find_similar_memories(keyword_threshold: int = 2):
    """Find memories with similar keywords"""
    print(f"🔍 Finding memories with {keyword_threshold}+ common keywords...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/memories/_dedup_analyze")
            response.raise_for_status()
            data = response.json()
            
            key_name = f"{keyword_threshold}_keywords"
            if key_name in data["statistics"]["keyword_overlaps"]:
                count = data["statistics"]["keyword_overlaps"][key_name]
                print(f"Found {count} memory pairs with {keyword_threshold}+ common keywords")
                
                if "sample_high_overlap_pairs" in data and data["sample_high_overlap_pairs"]:
                    print("\n📝 Sample pairs:")
                    for i, (mem1, mem2, overlap) in enumerate(data["sample_high_overlap_pairs"][:10], 1):
                        if overlap >= keyword_threshold:
                            print(f"  {i:2d}. {overlap} keywords: {mem1[:8]}...{mem1[-8:]} ↔ {mem2[:8]}...{mem2[-8:]}")
            else:
                print(f"❌ No data available for {keyword_threshold} keyword threshold")
                
        except httpx.HTTPError as e:
            print(f"❌ Error finding similar memories: {e}")
            return False
    
    return True

async def run_semantic_deduplication(similarity: float = 0.65, max_clusters: int = 5):
    """Run semantic deduplication using sentence-transformers"""
    print(f"🧠 Running semantic deduplication with {similarity:.2f} similarity threshold...")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(
                f"{BASE_URL}/memories/_dedup_semantic",
                params={
                    "semantic_similarity_threshold": similarity,
                    "max_clusters_to_process": max_clusters
                }
            )
            response.raise_for_status()
            data = response.json()
            
            print("\n🎯 SEMANTIC DEDUPLICATION RESULTS")
            print("=" * 50)
            
            if data["status"] == "completed":
                results = data.get("semantic_dedup_results", {})
                stats = data.get("stats", {})
                
                print(f"Total memories analyzed: {stats.get('memory_candidates_analyzed', 0)}")
                print(f"Semantic clusters found: {stats.get('semantic_clusters_found', 0)}")
                print(f"Clusters processed by LLM: {results.get('processed_clusters', 0)}")
                
                # Count total updates and deletions
                total_updates = 0
                total_deletions = 0
                for result in results.get("results", []):
                    total_updates += result.get("update_count", 0)
                    total_deletions += result.get("delete_count", 0)
                
                print(f"Memory updates: {total_updates}")
                print(f"Memory deletions: {total_deletions}")
                print(f"Net reduction: {total_deletions} memories")
                
                if results.get("results"):
                    print(f"\n📊 Summary:")
                    print(f"   {results['processed_clusters']} clusters processed, {total_updates + total_deletions} memories consolidated.")
            else:
                status_msg = data.get("message", data.get("status", "Unknown error"))
                print(f"❌ Semantic deduplication: {status_msg}")
                if "stats" in data:
                    stats = data["stats"]
                    print(f"   Analyzed {stats.get('memory_candidates', 0)} candidates with threshold {stats.get('semantic_similarity_threshold', 'unknown')}")
                return False
                
        except httpx.HTTPError as e:
            print(f"❌ Error running semantic deduplication: {e}")
            return False
        except asyncio.TimeoutError:
            print("⏰ Semantic deduplication timed out - it may still be running")
            return False
    
    return True

async def run_semantic_scan(similarity: float = 0.7, min_cluster_size: int = 3, max_clusters: int = 5):
    """Run semantic message scanning using clustering"""
    print(f"📡 Running semantic scan with {similarity:.2f} similarity threshold...")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(
                f"{BASE_URL}/memories/_scan_semantic",
                params={
                    "similarity_threshold": similarity,
                    "min_cluster_size": min_cluster_size,
                    "max_clusters_to_process": max_clusters
                }
            )
            response.raise_for_status()
            data = response.json()
            
            print("\n🎯 SEMANTIC SCAN RESULTS")
            print("=" * 50)
            
            if data["status"] == "ok":
                details = data.get("details", {})
                print(f"Total messages processed: {details.get('total_messages', 0)}")
                print(f"Semantic clusters found: {details.get('clusters_found', 0)}")
                print(f"Clusters processed by LLM: {details.get('clusters_processed', 0)}")
                print(f"Memories added: {details.get('memories_added', 0)}")
                
                print(f"\n📊 Summary:")
                print(f"   {data.get('message', 'No message')}")
            else:
                print(f"❌ Semantic scan failed: {data.get('message', 'Unknown error')}")
                return False
                
        except httpx.HTTPError as e:
            print(f"❌ Error running semantic scan: {e}")
            return False
        except asyncio.TimeoutError:
            print("⏰ Semantic scan timed out - it may still be running")
            return False
    
    return True

async def preview_semantic_scan(similarity: float = 0.7, min_cluster_size: int = 3, max_clusters: int = 5):
    """Preview what would be processed in semantic scan"""
    print(f"🔍 Previewing semantic scan with {similarity:.2f} similarity threshold...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/memories/_scan_semantic/preview",
                params={
                    "similarity_threshold": similarity,
                    "min_cluster_size": min_cluster_size,
                    "max_clusters_to_process": max_clusters
                }
            )
            response.raise_for_status()
            preview = response.json()
            
            print("\n📊 SEMANTIC SCAN PREVIEW")
            print("=" * 50)
            
            if preview.get("clusters"):
                print(f"Total untagged messages: {preview.get('total_messages', 0)}")
                print(f"Semantic clusters found: {preview.get('total_clusters_found', 0)}")
                print(f"Clusters that would be processed: {preview.get('clusters_would_process', 0)}")
                print(f"Messages that would be processed: {preview.get('messages_would_process', 0)}")
                
                config = preview.get("config", {})
                print(f"\n⚙️  CLUSTERING CONFIGURATION:")
                print(f"   Similarity threshold: {config.get('similarity_threshold', 0):.2f}")
                print(f"   Min cluster size: {config.get('min_cluster_size', 0)}")
                print(f"   Max clusters to process: {config.get('max_clusters_to_process', 0)}")
                
                # Show cluster details
                for cluster in preview["clusters"]:
                    print(f"\n   📁 Cluster {cluster['cluster_id']} ({cluster['message_count']} messages, density: {cluster['density']:.3f}):")
                    time_range = cluster.get("time_range", {})
                    if time_range.get("start") and time_range.get("end"):
                        print(f"      ⏰ Time range: {time_range['start']} to {time_range['end']}")
                    
                    for sample in cluster.get("sample_messages", []):
                        print(f"      💬 {sample}")
                
                print(f"\n💡 RECOMMENDATION:")
                cluster_count = preview.get('clusters_would_process', 0)
                if cluster_count > 10:
                    print(f"   ⚠️  {cluster_count} clusters is quite high!")
                    print(f"   Consider increasing similarity threshold to {similarity + 0.1:.1f}")
                elif cluster_count == 0:
                    print(f"   ℹ️  No clusters to process with current settings")
                    print(f"   Consider lowering similarity threshold to {max(0.5, similarity - 0.1):.1f}")
                else:
                    print(f"   ✅ {cluster_count} clusters seems reasonable for processing")
            else:
                reason = preview.get("reason", "No clusters found")
                print(f"❌ {reason}")
                
        except httpx.HTTPError as e:
            print(f"❌ Error getting semantic scan preview: {e}")
            return False
    
    return True

async def run_topic_deduplication_semantic(similarity: float = 0.7, max_clusters: int = 10):
    """Run semantic topic deduplication"""
    print(f"🏷️  Running semantic topic deduplication with {similarity:.2f} similarity threshold...")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(
                f"{BASE_URL}/topics/_dedup_semantic",
                params={
                    "semantic_similarity_threshold": similarity,
                    "max_clusters_to_process": max_clusters
                }
            )
            response.raise_for_status()
            data = response.json()
            
            print("\n🎯 TOPIC DEDUPLICATION RESULTS")
            print("=" * 50)
            
            if data["status"] == "completed":
                results = data.get("topic_dedup_results", {})
                stats = data.get("stats", {})
                
                print(f"Total topics analyzed: {stats.get('topics_analyzed', 0)}")
                print(f"Semantic clusters found: {stats.get('semantic_clusters_found', 0)}")
                print(f"Clusters processed by LLM: {results.get('processed_clusters', 0)}")
                print(f"Topics merged: {stats.get('topics_merged', 0)}")
                print(f"Memories moved: {stats.get('memories_moved', 0)}")
                
                if results.get("results"):
                    print(f"\n📊 Merged Topics:")
                    for result in results["results"]:
                        merge_result = result["merge_result"]
                        print(f"   → {merge_result['primary_topic_name']} (kept)")
                        print(f"     Absorbed {len(merge_result['deleted_topics'])} topics, moved {merge_result['moved_memories']} memories")
                        
            else:
                status_msg = data.get("message", data.get("status", "Unknown error"))
                print(f"❌ Topic deduplication: {status_msg}")
                return False
                
        except httpx.HTTPError as e:
            print(f"❌ Error running topic deduplication: {e}")
            return False
        except asyncio.TimeoutError:
            print("⏰ Topic deduplication timed out")
            return False
    
    return True

async def preview_topic_deduplication_semantic(similarity: float = 0.7, max_clusters: int = 10):
    """Preview semantic topic deduplication"""
    print(f"🔍 Previewing semantic topic deduplication with {similarity:.2f} similarity threshold...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/topics/_dedup_semantic/preview",
                params={
                    "semantic_similarity_threshold": similarity,
                    "max_clusters_to_process": max_clusters
                }
            )
            response.raise_for_status()
            data = response.json()
            
            print("\n📊 TOPIC DEDUPLICATION PREVIEW")
            print("=" * 50)
            
            if data["status"] == "preview":
                print(f"Total topics: {data.get('total_topics', 0)}")
                print(f"Semantic clusters found: {data.get('semantic_clusters_found', 0)}")
                print(f"Clusters that would be processed: {data.get('clusters_that_would_be_processed', 0)}")
                
                print("\n🏷️  TOPIC CLUSTERS:")
                for cluster in data.get("preview_clusters", [])[:3]:  # Show first 3
                    print(f"   Cluster {cluster['cluster_index']} ({cluster['topic_count']} topics, density: {cluster['density']:.3f}):")
                    for topic in cluster["topics"]:
                        print(f"     • {topic['name']} ({topic['memory_count']} memories)")
                    print()
                    
                if len(data.get("preview_clusters", [])) > 3:
                    remaining = len(data["preview_clusters"]) - 3
                    print(f"   ... and {remaining} more clusters")
                    
            else:
                print(f"❌ No topic clusters found: {data.get('message', 'Unknown')}")
                return False
                
        except httpx.HTTPError as e:
            print(f"❌ Error getting topic preview: {e}")
            return False
    
    return True

async def run_topic_based_deduplication(
    topic_similarity: float = 0.8,
    min_keyword_overlap: int = 2,
    max_keyword_overlap: int = 10,
    max_topic_groups: int = 20,
    max_memory_groups: int = 50,
    max_total_tokens: int = 100000,
    dry_run: bool = False
):
    """Run topic-based memory deduplication"""
    action = "Previewing" if dry_run else "Running"
    print(f"🎯 {action} topic-based memory deduplication...")
    print(f"   Topic similarity threshold: {topic_similarity}")
    print(f"   Keyword overlap range: {min_keyword_overlap}-{max_keyword_overlap}")
    print(f"   Max topic groups: {max_topic_groups}")
    print(f"   Max memory groups: {max_memory_groups}")
    print(f"   Max total tokens: {max_total_tokens:,}")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            params = {
                "topic_similarity_threshold": topic_similarity,
                "min_keyword_overlap": min_keyword_overlap,
                "max_keyword_overlap": max_keyword_overlap,
                "max_topic_groups": max_topic_groups,
                "max_memory_groups": max_memory_groups,
                "max_total_tokens": max_total_tokens,
                "dry_run": dry_run
            }
            
            response = await client.post(
                f"{BASE_URL}/memories/_dedup_topic_based",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            if dry_run:
                print("\n📊 TOPIC-BASED DEDUPLICATION PLAN")
                print("=" * 60)
                
                plan = data["plan"]
                print(f"Total topics: {plan['total_topics']}")
                print(f"Topic groups to consolidate: {plan['topic_groups_to_consolidate']}")
                print(f"Memory groups to deduplicate: {plan['memory_groups_to_deduplicate']}")
                print(f"Estimated LLM requests: {plan['estimated_llm_requests']}")
                print(f"Estimated total tokens: {plan['estimated_total_tokens']:,}")
                
                print("\n🏷️  TOPIC CONSOLIDATIONS:")
                for i, tc in enumerate(data.get("topic_consolidations", [])[:10], 1):
                    similar_names = ", ".join(tc["similar_topics"])
                    print(f"  {i:2d}. {tc['primary_topic']} + [{similar_names}]")
                    print(f"      ({tc['total_memories']} memories, similarity: {tc['similarity_score']:.2f})")
                
                print("\n🧠 MEMORY GROUPS:")
                for i, mg in enumerate(data.get("memory_groups", [])[:10], 1):
                    topic_names = ", ".join(mg["topic_names"])
                    print(f"  {i:2d}. {mg['memory_count']} memories from: {topic_names}")
                    print(f"      (keyword overlap: {mg['keyword_overlap']}, tokens: {mg['estimated_tokens']:,})")
                
                print(f"\n💰 ESTIMATED COST:")
                print(f"   Total LLM requests: {plan['estimated_llm_requests']}")
                print(f"   Total tokens: {plan['estimated_total_tokens']:,}")
                
            else:
                print("\n✅ TOPIC-BASED DEDUPLICATION COMPLETED")
                print("=" * 50)
                
                tc_results = data.get("topic_consolidation_results", {})
                print(f"Topics consolidated: {tc_results.get('merged_topic_groups', 0)}")
                print(f"Topics skipped: {tc_results.get('skipped_topic_groups', 0)}")
                
                md_results = data.get("memory_deduplication_results", {})
                print(f"Memory groups processed: {md_results.get('processed_groups', 0)}")
                
                stats = data.get("execution_stats", {})
                print(f"Total LLM requests made: {stats.get('total_llm_requests', 0)}")
                print(f"Estimated tokens used: {stats.get('estimated_tokens_used', 0):,}")
            
        except httpx.HTTPError as e:
            print(f"❌ Error in topic-based deduplication: {e}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    print(f"   Details: {error_data.get('detail', 'Unknown error')}")
                except:
                    pass
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False
    
    return True

async def consolidate_all_topics(dry_run: bool = True, max_topics_per_request: int = 20):
    """Analyze all topics for consolidation"""
    action = "Analyzing" if dry_run else "Consolidating"
    print(f"🏷️  {action} all topics for better organization...")
    print(f"   Max topics per LLM request: {max_topics_per_request}")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            params = {
                "dry_run": dry_run,
                "max_topics_per_request": max_topics_per_request
            }
            
            response = await client.post(
                f"{BASE_URL}/topics/_consolidate_all",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            if dry_run:
                print("\n📊 TOPIC CONSOLIDATION ANALYSIS")
                print("=" * 50)
                
                analysis = data["analysis"]
                print(f"Total topics: {analysis['total_topics']}")
                print(f"Estimated LLM requests: {analysis['estimated_llm_requests']}")
                print(f"Estimated tokens: {analysis['estimated_tokens']:,}")
                print(f"Topics per request: {analysis['topics_per_request']}")
                
                print("\n🏷️  TOPIC PREVIEW (Top 20 by memory count):")
                for i, topic in enumerate(data.get("topic_preview", []), 1):
                    print(f"  {i:2d}. {topic['name'][:50]:<50} ({topic['memory_count']} memories)")
                
                print(f"\n💰 ESTIMATED COST:")
                print(f"   LLM requests: {analysis['estimated_llm_requests']}")
                print(f"   Tokens: {analysis['estimated_tokens']:,}")
                
            else:
                print("\n✅ TOPIC CONSOLIDATION ANALYSIS COMPLETED")
                print("=" * 50)
                
                summary = data.get("summary", {})
                print(f"Topics analyzed: {summary.get('total_topics_analyzed', 0)}")
                print(f"Chunks processed: {summary.get('chunks_processed', 0)}")
                print(f"LLM requests made: {summary.get('total_llm_requests', 0)}")
                
                suggestions = data.get("consolidation_suggestions", [])
                print(f"\n📋 CONSOLIDATION SUGGESTIONS:")
                for i, suggestion in enumerate(suggestions[:5], 1):
                    print(f"  Chunk {suggestion.get('chunk_number', i)}:")
                    
                    # Show consolidations
                    consolidations = suggestion.get("consolidations", [])
                    if consolidations:
                        print("    Merge suggestions:")
                        for cons in consolidations[:3]:
                            topics = ", ".join(cons.get("topics_to_merge", []))
                            print(f"      • {topics} → {cons.get('new_name', 'N/A')}")
                    
                    # Show renames
                    renames = suggestion.get("renames", [])
                    if renames:
                        print("    Rename suggestions:")
                        for rename in renames[:3]:
                            print(f"      • {rename.get('old_name', 'N/A')} → {rename.get('new_name', 'N/A')}")
            
        except httpx.HTTPError as e:
            print(f"❌ Error in topic consolidation: {e}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    print(f"   Details: {error_data.get('detail', 'Unknown error')}")
                except:
                    pass
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Memory deduplication analysis and management for Kirishima",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s analyze                            # Analyze deduplication potential
  %(prog)s preview --keywords 3               # Preview what would be processed
  %(prog)s deduplicate                        # Run enhanced deduplication
  %(prog)s dedup-semantic --similarity 0.8    # Run semantic deduplication
  %(prog)s scan-semantic --clusters 3         # Run semantic message scanning
  %(prog)s preview-semantic --similarity 0.7  # Preview semantic scan
  %(prog)s stats                              # Show basic statistics
  %(prog)s similar --keywords 3               # Find memories with 3+ common keywords
        """
    )
    
    parser.add_argument(
        "command",
        choices=["analyze", "deduplicate", "dedup-semantic", "scan-semantic", "preview-semantic", "dedup-topics", "preview-topics", "dedup-topic-based", "preview-topic-based", "consolidate-topics", "stats", "similar"],
        help="Command to execute"
    )
    
    parser.add_argument(
        "--keywords",
        type=int,
        default=2,
        help="Minimum keyword overlap threshold (default: 2)"
    )
    
    parser.add_argument(
        "--similarity",
        type=float,
        default=0.7,
        help="Similarity threshold for semantic operations (0.0-1.0, default: 0.7)"
    )
    
    parser.add_argument(
        "--clusters",
        type=int,
        default=5,
        help="Maximum clusters to process in semantic operations (default: 5)"
    )
    
    parser.add_argument(
        "--min-cluster-size",
        type=int,
        default=3,
        help="Minimum cluster size for semantic scan (default: 3)"
    )
    
    args = parser.parse_args()
    
    try:
        if args.command == "analyze":
            success = asyncio.run(analyze_dedup_potential())
        elif args.command == "deduplicate":
            success = asyncio.run(run_enhanced_deduplication())
        elif args.command == "dedup-semantic":
            success = asyncio.run(run_semantic_deduplication(args.similarity, args.clusters))
        elif args.command == "scan-semantic":
            success = asyncio.run(run_semantic_scan(args.similarity, args.min_cluster_size, args.clusters))
        elif args.command == "preview-semantic":
            success = asyncio.run(preview_semantic_scan(args.similarity, args.min_cluster_size, args.clusters))
        elif args.command == "dedup-topics":
            success = asyncio.run(run_topic_deduplication_semantic(args.similarity, args.clusters))
        elif args.command == "preview-topics":
            success = asyncio.run(preview_topic_deduplication_semantic(args.similarity, args.clusters))
        elif args.command == "dedup-topic-based":
            success = asyncio.run(run_topic_based_deduplication(
                topic_similarity=args.similarity,
                min_keyword_overlap=args.keywords,
                max_keyword_overlap=args.keywords + 8,
                dry_run=False
            ))
        elif args.command == "preview-topic-based":
            success = asyncio.run(run_topic_based_deduplication(
                topic_similarity=args.similarity,
                min_keyword_overlap=args.keywords,
                max_keyword_overlap=args.keywords + 8,
                dry_run=True
            ))
        elif args.command == "consolidate-topics":
            success = asyncio.run(consolidate_all_topics(dry_run=True))
        elif args.command == "preview":
            success = asyncio.run(preview_deduplication(args.keywords, args.clusters))
        elif args.command == "stats":
            success = asyncio.run(show_basic_stats())
        elif args.command == "similar":
            success = asyncio.run(find_similar_memories(args.keywords))
        elif args.command == "topic-dedup-semantic":
            success = asyncio.run(run_topic_deduplication_semantic(args.similarity, args.clusters))
        elif args.command == "preview-topic-dedup-semantic":
            success = asyncio.run(preview_topic_deduplication_semantic(args.similarity, args.clusters))
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
