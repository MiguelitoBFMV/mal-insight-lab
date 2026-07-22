from django import forms

from games.models import (
    Game,
    GameAccess,
    GameContent,
    LibraryEntry,
    Playthrough,
)

MANUAL_LIBRARY_STATUS_CHOICES = tuple(
    (
        value,
        label,
    )
    for value, label in LibraryEntry.Status.choices
    if value not in {
        LibraryEntry.Status.PLAYING,
        LibraryEntry.Status.PAUSED,
    }
)

class LibraryEntryOwnerForm(forms.ModelForm):
    class Meta:
        model = LibraryEntry
        fields = (
            "status",
            "has_platinum",
            "main_story_hours_override",
            "notes",
        )
        labels = {
            "status": "Library Status",
            "has_platinum": "Platinum Unlocked",
            "main_story_hours_override": (
                "Manual Main Story Duration"
            ),
            "notes": "Library Notes",
        }
        widgets = {
            "status": forms.Select(
                attrs={
                    "class": "detail-owner-control",
                }
            ),
            "has_platinum": forms.CheckboxInput(
                attrs={
                    "class": "detail-owner-checkbox",
                }
            ),
            "main_story_hours_override": (
                forms.NumberInput(
                    attrs={
                        "class": "detail-owner-control",
                        "min": "0.1",
                        "step": "0.1",
                        "placeholder": "Hours",
                    }
                )
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": (
                        "detail-owner-control "
                        "detail-owner-textarea"
                    ),
                    "rows": 4,
                    "placeholder": (
                        "Personal context, priorities or notes..."
                    ),
                }
            ),
        }

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.has_playthroughs = bool(
            self.instance.pk
            and self.instance.playthroughs.exists()
        )

        if self.has_playthroughs:
            self.fields["status"].disabled = True
            self.fields["status"].help_text = (
                "This status is controlled by the "
                "playthrough history."
            )
        else:
            self.fields["status"].help_text = (
                "Playing and Paused require an active "
                "playthrough."
            )

    def clean(self):
        cleaned_data = super().clean()

        status = cleaned_data.get("status")
        has_platinum = cleaned_data.get(
            "has_platinum"
        )
        manual_hours = cleaned_data.get(
            "main_story_hours_override"
        )

        has_owned_access = bool(
            self.instance.pk
            and self.instance.accesses.filter(
                access_type=(
                    GameAccess.AccessType.OWNED
                ),
            ).exists()
        )

        if (
            not self.has_playthroughs
            and status
            in {
                LibraryEntry.Status.PLAYING,
                LibraryEntry.Status.PAUSED,
            }
        ):
            self.add_error(
                "status",
                (
                    "Playing and Paused require a "
                    "playthrough. Start one from the "
                    "playthrough controls."
                ),
            )

        if (
            status
            == LibraryEntry.Status.MULTIPLAYER
            and manual_hours is not None
        ):
            self.add_error(
                "main_story_hours_override",
                (
                    "Persistent multiplayer games do not use "
                    "a main-story duration."
                ),
            )

        if (
            status
            == LibraryEntry.Status.MULTIPLAYER
            and not has_owned_access
        ):
            self.add_error(
                "status",
                (
                    "A multiplayer entry must keep "
                    "at least one Owned access."
                ),
            )

        if (
            has_platinum
            and not has_owned_access
        ):
            self.add_error(
                "has_platinum",
                (
                    "Platinum can only be marked while "
                    "the game has at least one Owned access."
                ),
            )

        return cleaned_data
    

class GameAccessChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, access):
        platform = access.get_platform_name_display()

        if access.store:
            return (
                f"{platform} · "
                f"{access.get_store_display()}"
            )

        return platform


class PlaythroughOwnerForm(forms.ModelForm):
    access = GameAccessChoiceField(
        queryset=GameAccess.objects.none(),
        required=False,
        label="Platform & Store",
        widget=forms.Select(
            attrs={
                "class": "detail-owner-control",
            }
        ),
    )

    class Meta:
        model = Playthrough
        fields = (
            "access",
            "text_language",
            "progress_note",
            "started_on",
            "finished_on",
            "hours_played",
            "notes",
        )
        labels = {
            "text_language": "Text Language",
            "progress_note": "Progress",
            "started_on": "Started On",
            "finished_on": "Finished On",
            "hours_played": "Hours Played",
            "notes": "Playthrough Notes",
        }
        widgets = {
            "text_language": forms.Select(
                attrs={
                    "class": "detail-owner-control",
                }
            ),
            "progress_note": forms.TextInput(
                attrs={
                    "class": "detail-owner-control",
                    "placeholder": (
                        "Chapter, percentage or current point..."
                    ),
                }
            ),
            "started_on": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "detail-owner-control",
                    "type": "date",
                },
            ),
            "finished_on": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "detail-owner-control",
                    "type": "date",
                },
            ),
            "hours_played": forms.NumberInput(
                attrs={
                    "class": "detail-owner-control",
                    "min": "0.1",
                    "step": "0.1",
                    "placeholder": "Hours",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": (
                        "detail-owner-control "
                        "detail-owner-textarea"
                    ),
                    "rows": 3,
                    "placeholder": (
                        "Language experience, impressions "
                        "or context for this run..."
                    ),
                }
            ),
        }

    def __init__(
        self,
        *args,
        library_entry,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.library_entry = library_entry

        self.fields["access"].queryset = (
            GameAccess.objects
            .filter(
                library_entry=library_entry,
                access_type=GameAccess.AccessType.OWNED,
            )
            .order_by(
                "platform_name",
                "store",
            )
        )

    def clean(self):
        cleaned_data = super().clean()

        access = cleaned_data.get("access")
        finished_on = cleaned_data.get("finished_on")

        if (
            access is not None
            and access.library_entry_id
            != self.library_entry.pk
        ):
            self.add_error(
                "access",
                (
                    "The selected access does not belong "
                    "to this library entry."
                ),
            )

        if (
            self.instance.status
            in {
                Playthrough.Status.PLAYING,
                Playthrough.Status.PAUSED,
            }
            and finished_on is not None
        ):
            self.add_error(
                "finished_on",
                (
                    "An active or paused playthrough "
                    "cannot have a finish date."
                ),
            )

        return cleaned_data


class NewPlaythroughForm(forms.ModelForm):
    access = GameAccessChoiceField(
        queryset=GameAccess.objects.none(),
        required=True,
        label="Platform & Store",
        widget=forms.Select(
            attrs={
                "class": "detail-owner-control",
            }
        ),
    )

    class Meta:
        model = Playthrough
        fields = (
            "access",
            "text_language",
            "progress_note",
            "started_on",
            "notes",
        )
        labels = {
            "text_language": "Text Language",
            "progress_note": "Initial Progress",
            "started_on": "Started On",
            "notes": "Playthrough Notes",
        }
        widgets = {
            "text_language": forms.Select(
                attrs={
                    "class": "detail-owner-control",
                }
            ),
            "progress_note": forms.TextInput(
                attrs={
                    "class": "detail-owner-control",
                    "placeholder": (
                        "Chapter, percentage or starting point..."
                    ),
                }
            ),
            "started_on": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "detail-owner-control",
                    "type": "date",
                },
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": (
                        "detail-owner-control "
                        "detail-owner-textarea"
                    ),
                    "rows": 3,
                    "placeholder": (
                        "Language goal, replay context "
                        "or initial notes..."
                    ),
                }
            ),
        }

    def __init__(
        self,
        *args,
        library_entry,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.library_entry = library_entry

        self.fields["access"].queryset = (
            GameAccess.objects
            .filter(
                library_entry=library_entry,
                access_type=GameAccess.AccessType.OWNED,
            )
            .order_by(
                "platform_name",
                "store",
            )
        )

    def clean(self):
        cleaned_data = super().clean()

        if (
            self.library_entry.status
            == LibraryEntry.Status.MULTIPLAYER
        ):
            raise forms.ValidationError(
                (
                    "Persistent multiplayer games "
                    "do not use playthroughs."
                )
            )

        return cleaned_data

    
class GameAccessOwnerForm(forms.ModelForm):
    class Meta:
        model = GameAccess
        fields = (
            "access_type",
            "platform_name",
            "store",
            "notes",
        )
        labels = {
            "access_type": "Access Type",
            "platform_name": "Platform",
            "store": "Store",
            "notes": "Access Notes",
        }
        widgets = {
            "access_type": forms.Select(
                attrs={
                    "class": "detail-owner-control",
                }
            ),
            "platform_name": forms.Select(
                attrs={
                    "class": "detail-owner-control",
                }
            ),
            "store": forms.Select(
                attrs={
                    "class": "detail-owner-control",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": (
                        "detail-owner-control "
                        "detail-owner-textarea"
                    ),
                    "rows": 3,
                    "placeholder": (
                        "Optional context about this access..."
                    ),
                }
            ),
        }

    def __init__(
        self,
        *args,
        library_entry,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.library_entry = library_entry
        self.instance.library_entry = library_entry

        self.access_is_in_use = bool(
            self.instance.pk
            and Playthrough.objects.filter(
                access=self.instance,
            ).exists()
        )

        if self.access_is_in_use:
            for field_name in (
                "access_type",
                "platform_name",
                "store",
            ):
                self.fields[field_name].disabled = True

    def clean(self):
        cleaned_data = super().clean()

        access_type = cleaned_data.get("access_type")
        platform_name = cleaned_data.get("platform_name")
        store = cleaned_data.get("store", "")

        if access_type and platform_name:
            duplicate_access = GameAccess.objects.filter(
                library_entry=self.library_entry,
                access_type=access_type,
                platform_name=platform_name,
                store=store,
            )

            if self.instance.pk:
                duplicate_access = duplicate_access.exclude(
                    pk=self.instance.pk
                )

            if duplicate_access.exists():
                raise forms.ValidationError(
                    (
                        "This platform and store access "
                        "is already registered."
                    )
                )

        if (
            self.instance.pk
            and access_type != GameAccess.AccessType.OWNED
            and Playthrough.objects.filter(
                access=self.instance,
            ).exists()
        ):
            self.add_error(
                "access_type",
                (
                    "An access used by a playthrough "
                    "must remain Owned."
                ),
            )
    
        if (
            self.library_entry.has_platinum
            and access_type
            != GameAccess.AccessType.OWNED
        ):
            other_owned_accesses = (
                GameAccess.objects.filter(
                    library_entry=self.library_entry,
                    access_type=GameAccess.AccessType.OWNED,
                )
            )

            if self.instance.pk:
                other_owned_accesses = (
                    other_owned_accesses.exclude(
                        pk=self.instance.pk
                    )
                )

            if not other_owned_accesses.exists():
                self.add_error(
                    "access_type",
                    (
                        "A platinum-marked game must "
                        "keep at least one Owned access."
                    ),
                )

        return cleaned_data


class GameContentOwnerForm(forms.ModelForm):
    class Meta:
        model = GameContent
        fields = (
            "title",
            "content_type",
            "status",
            "completed_on",
            "notes",
        )
        labels = {
            "title": "Content Title",
            "content_type": "Content Type",
            "status": "Status",
            "completed_on": "Completed On",
            "notes": "Content Notes",
        }
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "detail-owner-control",
                    "placeholder": (
                        "Expansion, DLC or additional story..."
                    ),
                }
            ),
            "content_type": forms.Select(
                attrs={
                    "class": "detail-owner-control",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "detail-owner-control",
                }
            ),
            "completed_on": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "detail-owner-control",
                    "type": "date",
                },
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": (
                        "detail-owner-control "
                        "detail-owner-textarea"
                    ),
                    "rows": 3,
                    "placeholder": (
                        "Personal context, impressions "
                        "or plans for this content..."
                    ),
                }
            ),
        }

    def __init__(
        self,
        *args,
        library_entry,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.library_entry = library_entry
        self.instance.library_entry = library_entry

    def clean(self):
        cleaned_data = super().clean()

        title = str(
            cleaned_data.get("title") or ""
        ).strip()

        status = cleaned_data.get("status")
        completed_on = cleaned_data.get(
            "completed_on"
        )

        if title:
            duplicate_content = (
                GameContent.objects.filter(
                    library_entry=self.library_entry,
                    title__iexact=title,
                )
            )

            if self.instance.pk:
                duplicate_content = (
                    duplicate_content.exclude(
                        pk=self.instance.pk
                    )
                )

            if duplicate_content.exists():
                self.add_error(
                    "title",
                    (
                        "Content with this title is already "
                        "tracked under this game."
                    ),
                )

        if (
            completed_on
            and status
            != GameContent.Status.COMPLETED
        ):
            self.add_error(
                "completed_on",
                (
                    "A completion date can only be added "
                    "when the status is Completed."
                ),
            )

        return cleaned_data


class IGDBGameContentTrackForm(forms.Form):
    status = forms.ChoiceField(
        choices=GameContent.Status.choices,
        initial=GameContent.Status.PLAN_TO_PLAY,
        label="Status",
        widget=forms.Select(
            attrs={
                "class": "detail-owner-control",
            }
        ),
    )

    completed_on = forms.DateField(
        required=False,
        label="Completed On",
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "class": "detail-owner-control",
                "type": "date",
            },
        ),
    )

    notes = forms.CharField(
        required=False,
        label="Content Notes",
        widget=forms.Textarea(
            attrs={
                "class": (
                    "detail-owner-control "
                    "detail-owner-textarea"
                ),
                "rows": 3,
                "placeholder": (
                    "Why you want to track it, "
                    "when you played it or other context..."
                ),
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()

        status = cleaned_data.get("status")
        completed_on = cleaned_data.get(
            "completed_on"
        )

        if (
            completed_on
            and status
            != GameContent.Status.COMPLETED
        ):
            self.add_error(
                "completed_on",
                (
                    "A completion date can only be added "
                    "when the status is Completed."
                ),
            )

        return cleaned_data


class IGDBLinkExistingGameForm(forms.Form):
    existing_game = forms.ModelChoiceField(
        queryset=Game.objects.none(),
        required=True,
        label="Existing Local Game",
        empty_label="Select an unlinked local game...",
        widget=forms.Select(
            attrs={
                "class": "detail-owner-control",
            }
        ),
    )

    def __init__(
        self,
        *args,
        available_games,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.fields["existing_game"].queryset = (
            available_games
        )


class IGDBNewGameImportForm(forms.Form):
    status = forms.ChoiceField(
        choices=MANUAL_LIBRARY_STATUS_CHOICES,
        label="Library Status",
        widget=forms.Select(
            attrs={
                "class": "detail-owner-control",
            }
        ),
    )

    has_platinum = forms.BooleanField(
        required=False,
        label="Platinum Unlocked",
        widget=forms.CheckboxInput(
            attrs={
                "class": "detail-owner-checkbox",
            }
        ),
    )

    access_type = forms.ChoiceField(
        choices=GameAccess.AccessType.choices,
        label="Access Type",
        widget=forms.Select(
            attrs={
                "class": "detail-owner-control",
            }
        ),
    )

    platform_name = forms.ChoiceField(
        choices=GameAccess.Platform.choices,
        label="Platform",
        widget=forms.Select(
            attrs={
                "class": "detail-owner-control",
            }
        ),
    )

    store = forms.ChoiceField(
        choices=(
            (
                "",
                "No store / Not specified",
            ),
            *GameAccess.Store.choices,
        ),
        required=False,
        label="Store",
        widget=forms.Select(
            attrs={
                "class": "detail-owner-control",
            }
        ),
    )

    notes = forms.CharField(
        required=False,
        label="Library Notes",
        widget=forms.Textarea(
            attrs={
                "class": (
                    "detail-owner-control "
                    "detail-owner-textarea"
                ),
                "rows": 4,
                "placeholder": (
                    "Priority, context or reason "
                    "for adding this game..."
                ),
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()

        status = cleaned_data.get("status")
        access_type = cleaned_data.get(
            "access_type"
        )
        has_platinum = cleaned_data.get(
            "has_platinum"
        )

        if (
            status
            == LibraryEntry.Status.MULTIPLAYER
            and access_type
            != GameAccess.AccessType.OWNED
        ):
            self.add_error(
                "access_type",
                (
                    "A game marked as Multiplayer "
                    "must have an Owned access."
                ),
            )

        if (
            has_platinum
            and access_type
            != GameAccess.AccessType.OWNED
        ):
            self.add_error(
                "has_platinum",
                (
                    "Platinum requires the first "
                    "platform access to be Owned. "
                    "Wishlist accesses can be added later."
                ),
            )

        return cleaned_data
    

