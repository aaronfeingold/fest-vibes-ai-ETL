import asyncio

from sqlalchemy import text

from src.main import DatabaseHandler


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
            print(f"\nEvent ID: {event.get('id', 'N/A')}")
            print(f"Artist: {event.get('artist', 'N/A')}")
            print(f"Venue: {event.get('venue', 'N/A')}")

            # Safely handle description embedding
            desc_embedding = event.get("description_embedding")
            if desc_embedding is not None:
                print(f"Description Embedding: {desc_embedding[:100]}...")
            else:
                print("Description Embedding: None")

            # Safely handle event text embedding
            event_embedding = event.get("event_text_embedding")
            if event_embedding is not None:
                print(f"Event Text Embedding: {event_embedding[:100]}...")
            else:
                print("Event Text Embedding: None")

            print("------------------------")

        await db_handler.close()

    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
