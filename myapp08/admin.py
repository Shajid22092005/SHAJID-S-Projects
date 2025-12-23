from django.contrib import admin
from .models import UserProfile
from .models import (
    Event,
    EventCategory,
    EventSchedule,
    EventMedia,
    TicketTier,
    Ticket,
    RSVP,
)

class EventScheduleInline(admin.TabularInline):
    model = EventSchedule
    extra = 1

class EventMediaInline(admin.TabularInline):
    model = EventMedia
    extra = 1

class TicketTierInline(admin.TabularInline):
    model = TicketTier
    extra = 1

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "location", "category")
    list_filter = ("category", "date")
    search_fields = ("title", "location", "description")
    inlines = [TicketTierInline, EventScheduleInline, EventMediaInline]

@admin.register(EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("event", "email", "tier", "quantity", "total_amount", "code", "created_at")
    list_filter = ("event", "tier", "created_at")
    search_fields = ("email", "code")

@admin.register(RSVP)
class RSVPAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "status")
    list_filter = ("status", "event")
    search_fields = ("user__username", "event__title")




@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email")
