import Parser from 'rss-parser';
import * as crypto from 'crypto';

// Bypass SSL verification issues for local development feeds
process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";

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
    item: [
      ['media:thumbnail', 'mediaThumbnail'],
      ['media:content', 'mediaContent'],
      'enclosure',
      'content:encoded',
      'description'
    ]
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
  // 1. Check mediaThumbnail, mediaContent, enclosure
  for (const field of ['mediaThumbnail', 'mediaContent', 'enclosure']) {
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

export async function fetchNews(curateForHome: boolean = false): Promise<Article[]> {
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
  let uniqueArticles: Article[] = [];

  for (const article of articles.sort((a, b) => b.pubDate.getTime() - a.pubDate.getTime())) {
    const titleHash = crypto.createHash('md5').update(article.title.toLowerCase()).digest('hex');
    if (!seenUrls.has(article.link) && !seenTitles.has(titleHash)) {
      seenUrls.add(article.link);
      seenTitles.add(titleHash);
      uniqueArticles.push(article);
    }
  }

  if (!curateForHome) {
    return uniqueArticles;
  }

  // Home Page Curation Logic (70% AI/Best w/ image, 20% No image, 10% Politics/World)
  const totalTarget = 50;
  const politicsTarget = Math.floor(totalTarget * 0.10); // 5
  const noImageTarget = Math.floor(totalTarget * 0.20);  // 10
  const bestImageTarget = totalTarget - politicsTarget - noImageTarget; // 35

  const bucketPolitics: Article[] = [];
  const bucketNoImage: Article[] = [];
  const bucketBestImage: Article[] = [];
  const remaining: Article[] = [];

  for (const article of uniqueArticles) {
    const searchString = (article.title + " " + article.description).toLowerCase();
    const isPolitics = article.category === 'world' || /trump|modi|war|politics|election/.test(searchString);
    const hasImage = !!article.image;
    const isBest = ['technology', 'startups', 'science', 'space'].includes(article.category) || /ai|artificial intelligence/.test(searchString);

    if (isPolitics && bucketPolitics.length < politicsTarget) {
      bucketPolitics.push(article);
    } else if (!hasImage && bucketNoImage.length < noImageTarget) {
      bucketNoImage.push(article);
    } else if (hasImage && isBest && bucketBestImage.length < bestImageTarget) {
      bucketBestImage.push(article);
    } else {
      remaining.push(article);
    }
  }

  // If buckets aren't full, fill from remaining
  while (bucketPolitics.length < politicsTarget && remaining.length > 0) {
    bucketPolitics.push(remaining.shift()!);
  }
  while (bucketNoImage.length < noImageTarget && remaining.length > 0) {
    // Only pull articles without images if possible, otherwise just fill it
    const noImgIdx = remaining.findIndex(a => !a.image);
    if (noImgIdx >= 0) {
      bucketNoImage.push(remaining.splice(noImgIdx, 1)[0]);
    } else {
      bucketNoImage.push(remaining.shift()!);
    }
  }
  while (bucketBestImage.length < bestImageTarget && remaining.length > 0) {
    const imgIdx = remaining.findIndex(a => !!a.image);
    if (imgIdx >= 0) {
      bucketBestImage.push(remaining.splice(imgIdx, 1)[0]);
    } else {
      bucketBestImage.push(remaining.shift()!);
    }
  }

  const finalFeed = [...bucketPolitics, ...bucketNoImage, ...bucketBestImage];
  
  // Randomly shuffle the feed so categories and image-types are mixed
  for (let i = finalFeed.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [finalFeed[i], finalFeed[j]] = [finalFeed[j], finalFeed[i]];
  }

  return finalFeed;
}
