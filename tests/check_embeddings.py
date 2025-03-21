import asyncio
from main import DatabaseHandler
from sqlalchemy import text


async def main():
    try:
        # Initialize database handler
        db_handler = await DatabaseHandler.create()

        # First check total number of events
        async with db_handler.get_session() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM events"))
            count = result.scalar()
            print(f"\nTotal number of events in database: {count}")

        # Inspect embeddings
        embeddings = await db_handler.inspect_embeddings(limit=5)

        print("\nVector Embeddings Sample:")
        print("------------------------")
        for event in embeddings:
            print(f"\nEvent ID: {event['id']}")
            print(f"Artist: {event['artist']}")
            print(f"Venue: {event['venue']}")
            print(f"Description Embedding: {event['description_embedding'][:100]}...")  # Show first part only
            print(f"Event Text Embedding: {event['event_text_embedding'][:100]}...")  # Show first part only
            print("------------------------")

        await db_handler.close()

    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
