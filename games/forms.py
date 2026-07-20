from django import forms

from games.models import (
    GameAccess,
    LibraryEntry,
    Playthrough,
)


class LibraryEntryOwnerForm(forms.ModelForm):
    class Meta:
        model = LibraryEntry
        fields = (
            "has_platinum",
            "main_story_hours_override",
            "notes",
        )
        labels = {
            "has_platinum": "Platinum Unlocked",
            "main_story_hours_override": (
                "Manual Main Story Duration"
            ),
            "notes": "Library Notes",
        }
        widgets = {
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

    def clean(self):
        cleaned_data = super().clean()

        manual_hours = cleaned_data.get(
            "main_story_hours_override"
        )

        if (
            self.instance.status
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

        return cleaned_data
    
