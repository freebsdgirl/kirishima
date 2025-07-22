#!/usr/bin/env python3
"""
Generate a word cloud visualization from the heatmap keyword scores.

This script reads keyword scores from the ledger database and creates a visual
word cloud where the size of each word corresponds to its heatmap score.
"""

import sqlite3
import sys
import os
from pathlib import Path
from typing import Dict, Optional

try:
    from wordcloud import WordCloud
    import matplotlib.pyplot as plt
except ImportError:
    print("Required packages not installed. Please install with:")
    print("pip install wordcloud matplotlib")
    sys.exit(1)

# Database path relative to scripts directory
DB_PATH = "../shared/db/ledger/buffer.db"


def get_keyword_scores() -> Dict[str, float]:
    """
    Fetch keyword scores from the heatmap database.
    
    Returns:
        Dictionary mapping keywords to their scores
    """
    db_file = Path(__file__).parent / DB_PATH
    
    if not db_file.exists():
        raise FileNotFoundError(f"Database not found at: {db_file}")
    
    try:
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        
        # Check if heatmap_score table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='heatmap_score'
        """)
        
        if not cursor.fetchone():
            print("Warning: heatmap_score table not found in database")
            conn.close()
            return {}
        
        # Get all keyword scores
        cursor.execute("SELECT keyword, score FROM heatmap_score ORDER BY score DESC")
        scores = dict(cursor.fetchall())
        
        conn.close()
        return scores
        
    except sqlite3.Error as e:
        raise Exception(f"Database error: {e}")


def create_wordcloud(keyword_scores: Dict[str, float], 
                    output_file: Optional[str] = None,
                    width: int = 1200, 
                    height: int = 600) -> None:
    """
    Create and save a word cloud from keyword scores.
    
    Args:
        keyword_scores: Dictionary mapping keywords to scores
        output_file: Output file path (defaults to heatmap_wordcloud.png)
        width: Word cloud width in pixels
        height: Word cloud height in pixels
    """
    if not keyword_scores:
        print("No keyword scores found. The heatmap may be empty.")
        return
    
    if output_file is None:
        output_file = "heatmap_wordcloud.png"
    
    # Create word cloud
    # Scale scores to make visualization more readable (multiply by 100)
    scaled_scores = {word: score * 100 for word, score in keyword_scores.items()}
    
    wordcloud = WordCloud(
        width=width,
        height=height,
        background_color='white',
        max_words=100,
        relative_scaling=0.5,
        colormap='viridis',
        prefer_horizontal=0.7
    ).generate_from_frequencies(scaled_scores)
    
    # Create matplotlib figure
    plt.figure(figsize=(width/100, height/100))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    plt.title('Keyword Heatmap Visualization', fontsize=16, pad=20)
    
    # Add score info as subtitle
    max_score = max(keyword_scores.values()) if keyword_scores else 0
    min_score = min(keyword_scores.values()) if keyword_scores else 0
    plt.figtext(0.5, 0.02, 
                f'Keywords: {len(keyword_scores)} | Score range: {min_score:.2f} - {max_score:.2f}',
                ha='center', fontsize=10)
    
    # Save the image
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Word cloud saved to: {output_file}")
    
    # Optionally display if running interactively
    if len(sys.argv) == 1 or '--show' in sys.argv:
        plt.show()
    
    plt.close()


def print_keyword_stats(keyword_scores: Dict[str, float]) -> None:
    """Print summary statistics about the keywords."""
    if not keyword_scores:
        print("No keywords found in heatmap.")
        return
    
    print(f"\nKeyword Heatmap Statistics:")
    print(f"Total keywords: {len(keyword_scores)}")
    print(f"Score range: {min(keyword_scores.values()):.3f} - {max(keyword_scores.values()):.3f}")
    print(f"Average score: {sum(keyword_scores.values()) / len(keyword_scores):.3f}")
    
    # Show top 10 keywords
    sorted_keywords = sorted(keyword_scores.items(), key=lambda x: x[1], reverse=True)
    print(f"\nTop 10 keywords:")
    for i, (keyword, score) in enumerate(sorted_keywords[:10], 1):
        print(f"  {i:2d}. {keyword:<20} {score:.3f}")


def main():
    """Main function to generate word cloud from heatmap data."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate word cloud from heatmap keyword scores")
    parser.add_argument('-o', '--output', help='Output file path (default: heatmap_wordcloud.png)')
    parser.add_argument('-w', '--width', type=int, default=1200, help='Word cloud width (default: 1200)')
    parser.add_argument('--height', type=int, default=600, help='Word cloud height (default: 600)')
    parser.add_argument('--show', action='store_true', help='Display the word cloud after generating')
    parser.add_argument('--stats-only', action='store_true', help='Only print statistics, don\'t generate word cloud')
    
    args = parser.parse_args()
    
    try:
        print("Fetching keyword scores from heatmap database...")
        keyword_scores = get_keyword_scores()
        
        print_keyword_stats(keyword_scores)
        
        if not args.stats_only and keyword_scores:
            print(f"\nGenerating word cloud...")
            create_wordcloud(
                keyword_scores, 
                output_file=args.output,
                width=args.width,
                height=args.height
            )
        elif args.stats_only:
            print("Stats-only mode: skipping word cloud generation.")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
