import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .models import Exchange, ExchangeMessage, Notification


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.exchange_id = self.scope["url_route"]["kwargs"]["exchange_id"]
        self.room_group_name = f"chat_{self.exchange_id}"
        self.user = self.scope.get("user")

        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        is_participant = await self.check_participant(self.exchange_id, self.user)
        if not is_participant:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            content = data.get("content", "").strip()
            if not content:
                return

            saved_msg = await self.save_message(self.exchange_id, self.user, content)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "id": saved_msg["id"],
                    "author": saved_msg["author"],
                    "author_id": self.user.pk,
                    "content": saved_msg["content"],
                    "created_at": saved_msg["created_at"],
                },
            )
        except Exception:
            pass

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps({
                "id": event["id"],
                "author": event["author"],
                "content": event["content"],
                "created_at": event["created_at"],
                "is_mine": event["author_id"] == self.user.pk,
            })
        )

    @database_sync_to_async
    def check_participant(self, exchange_id, user):
        try:
            exchange = Exchange.objects.get(pk=exchange_id)
            return exchange.includes(user)
        except Exchange.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, exchange_id, user, content):
        exchange = Exchange.objects.get(pk=exchange_id)
        msg = ExchangeMessage.objects.create(
            exchange=exchange,
            author=user,
            content=content[:2000],
        )
        partner = exchange.partner_for(user)
        if partner:
            Notification.objects.create(
                recipient=partner,
                actor=user,
                notification_type=Notification.NotificationType.MESSAGE_RECEIVED,
                title=f"New message from {user.get_full_name() or user.username}",
                message=content[:100],
                link=f"/exchanges/{exchange.pk}/learn/",
            )
        return {
            "id": msg.pk,
            "author": user.get_full_name() or user.username,
            "content": msg.content,
            "created_at": timezone.localtime(msg.created_at).isoformat(),
        }

