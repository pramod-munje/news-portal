import Parser from 'rss-parser';

const parser = new Parser({
  customFields: {
    item: [
      ['media:thumbnail', 'mediaThumbnail'],
      ['media:content', 'mediaContent']
    ]
  }
});

async function test() {
  const feed = await parser.parseURL('https://feeds.bbci.co.uk/news/world/rss.xml');
  console.log(JSON.stringify(feed.items[0], null, 2));
}

test().catch(console.error);
