import Parser from 'rss-parser';
import * as crypto from 'crypto';

export interface Article {
  title: string;
  link: string;
  description: string;
  pubDate: Date;
  source: string;
  category: string;
  image: string;
  fallbackImage: string;
}

const FEEDS = [
  { source: 'BBC News', category: 'world', url: 'https://feeds.bbci.co.uk/news/world/rss.xml' },
  { source: 'BBC News', category: 'technology', url: 'https://feeds.bbci.co.uk/news/technology/rss.xml' },
  { source: 'BBC News', category: 'science', url: 'https://feeds.bbci.co.uk/news/science_and_environment/rss.xml' },
  { source: 'BBC News', category: 'business', url: 'https://feeds.bbci.co.uk/news/business/rss.xml' },
  { source: 'TechCrunch', category: 'startups', url: 'https://techcrunch.com/feed/' },
  { source: 'The Verge', category: 'technology', url: 'https://www.theverge.com/rss/index.xml' },
  { source: 'Wired', category: 'technology', url: 'https://www.wired.com/feed/rss' },
  { source: 'Ars Technica', category: 'technology', url: 'https://feeds.arstechnica.com/arstechnica/index' },
  { source: 'CNBC', category: 'business', url: 'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114' },
  { source: 'NASA', category: 'space', url: 'https://www.nasa.gov/feed/' },
  { source: 'Nature', category: 'science', url: 'https://www.nature.com/nature.rss' }
];

const parser = new Parser({
  customFields: {
    item: ['media:content', 'enclosure', 'content:encoded', 'description']
  }
});

function isTracker(url: string): boolean {
  const trackers = ['1x1', 'gravatar', 'doubleclick', 'pixel', 'analytics', 'spacer', 'feedburner', 'adsystem', 'facebook.com/tr', 'google-analytics', 'sharing', 'share_icon'];
  const lowerUrl = url.toLowerCase();
  return trackers.some(t => lowerUrl.includes(t));
}

function cleanAndUpgradeUrl(url: string | null): string | null {
  if (!url) return null;
  let cleanUrl = url.trim();
  if (cleanUrl.startsWith('//')) cleanUrl = 'https:' + cleanUrl;
  
  if (cleanUrl.includes('ichef.bbci.co.uk')) {
    cleanUrl = cleanUrl.replace('/standard/240/', '/standard/800/')
                       .replace('/standard/320/', '/standard/800/')
                       .replace('/240x135/', '/800x450/');
  }
  return cleanUrl;
}

function extractImage(item: any): string | null {
  // 1. Check media:content / enclosure
  for (const field of ['media:content', 'enclosure']) {
    if (item[field] && item[field].$) {
      const url = item[field].$.url;
      if (url && !isTracker(url)) return cleanAndUpgradeUrl(url);
    }
  }

  // 2. Check description or content:encoded for img tag
  const htmlContent = item['content:encoded'] || item.content || item.description || '';
  const imgMatch = htmlContent.match(/<img[^>]+src=["']([^"']+)["']/i);
  if (imgMatch && imgMatch[1]) {
    const url = imgMatch[1];
    if (!isTracker(url)) return cleanAndUpgradeUrl(url);
  }

  return null;
}

export function getFallbackImage(category: string): string {
  const categoryColors: Record<string, [string, string]> = {
    'ai-news': ['#1e1b4b', '#065f46'],
    'cybersecurity': ['#0f172a', '#831843'],
    'space': ['#000000', '#1e1b4b'],
    'robotics': ['#171717', '#0f766e'],
    'startups': ['#422006', '#86198f'],
    'technology': ['#020617', '#1d4ed8'],
    'business': ['#064e3b', '#0f172a'],
    'science': ['#2e1065', '#0f172a'],
    'world': ['#000000', '#000000'],
    'latest-news': ['#171717', '#171717']
  };

  const [c1, c2] = categoryColors[category] || ['#0f172a', '#1e1b4b'];
  const label = category.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450" viewBox="0 0 800 450">
<defs>
<linearGradient id="grad-${category}" x1="0%" y1="0%" x2="100%" y2="100%">
<stop offset="0%" stop-color="${c1}" />
<stop offset="100%" stop-color="${c2}" />
</linearGradient>
</defs>
<rect width="800" height="450" fill="url(#grad-${category})" />
<text x="400" y="225" font-family="system-ui, sans-serif" font-size="48" font-weight="bold" fill="#ffffff" text-anchor="middle" dominant-baseline="middle" opacity="0.8">
${label}
</text>
</svg>`;

  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

function cleanText(html: string): string {
  if (!html) return '';
  return html.replace(/<[^>]+>/g, '')
             .replace(/&[a-z]+;/gi, ' ')
             .replace(/\s+/g, ' ')
             .trim()
             .substring(0, 200) + '…'; // Added ... equivalent for truncation
}

export async function fetchNews(): Promise<Article[]> {
  const articles: Article[] = [];

  for (const feed of FEEDS) {
    try {
      const parsed = await parser.parseURL(feed.url);
      for (const item of parsed.items) {
        if (!item.title || !item.link) continue;
        
        const pubDate = item.pubDate ? new Date(item.pubDate) : new Date();
        // Ignore articles older than 3 days
        if (Date.now() - pubDate.getTime() > 3 * 24 * 60 * 60 * 1000) continue;

        const img = extractImage(item);
        
        articles.push({
          title: item.title.trim(),
          link: item.link.trim(),
          description: cleanText(item.description || item.contentSnippet || ''),
          pubDate,
          source: feed.source,
          category: feed.category,
          image: img || '',
          fallbackImage: getFallbackImage(feed.category)
        });
      }
    } catch (e) {
      console.error(`Failed to fetch ${feed.source} (${feed.url}):`, e);
    }
  }

  // Deduplicate by URL and Title
  const seenUrls = new Set<string>();
  const seenTitles = new Set<string>();
  const uniqueArticles: Article[] = [];

  for (const article of articles.sort((a, b) => b.pubDate.getTime() - a.pubDate.getTime())) {
    const titleHash = crypto.createHash('md5').update(article.title.toLowerCase()).digest('hex');
    if (!seenUrls.has(article.link) && !seenTitles.has(titleHash)) {
      seenUrls.add(article.link);
      seenTitles.add(titleHash);
      uniqueArticles.push(article);
    }
  }

  return uniqueArticles;
}
