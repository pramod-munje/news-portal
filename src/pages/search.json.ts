import { fetchNews } from '../lib/news';

export async function GET() {
  const articles = await fetchNews(false); // Fetch all articles, not just curated ones
  
  const searchIndex = articles.map(article => ({
    title: article.title,
    link: article.link,
    category: article.category || 'General',
    pubDate: article.pubDate.toISOString(),
    image: article.image
  }));
  
  return new Response(JSON.stringify(searchIndex), {
    headers: {
      'Content-Type': 'application/json'
    }
  });
}
