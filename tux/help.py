from collections.abc import Mapping
from typing import Any, get_type_hints

import discord
from discord.ext import commands
from loguru import logger

from tux.utils.constants import Constants as CONST
from tux.utils.embeds import EmbedCreator


class TuxHelp(commands.HelpCommand):
    def __init__(self):
        self.prefix = CONST.PREFIX
        super().__init__(
            command_attrs={
                "help": "Lists all categories and commands.",
                "aliases": ["h"],
                "usage": "$help <category> or <command>",
            },
        )

    def embed_base(self, title: str, description: str | None = None) -> discord.Embed:
        return discord.Embed(
            title=title,
            description=description,
            color=CONST.EMBED_COLORS["DEFAULT"],
        )

    def add_command_field(
        self,
        embed: discord.Embed,
        command: commands.Command[Any, Any, Any],
        prefix: str,
    ):
        embed.add_field(
            name=f"{prefix}{command.qualified_name} ({', '.join(command.aliases) if command.aliases else 'No aliases.'})",
            value=f"> {command.short_doc or 'No documentation summary.'}",
            inline=False,
        )

    def _get_flag_type(self, flag_annotation: Any) -> Any:
        if flag_annotation is None:
            return "Any"
        if isinstance(flag_annotation, type):
            return flag_annotation.__name__
        return flag_annotation

    def format_flag_name(self, flag: commands.Flag) -> str:
        return f"--[{flag.name}]" if flag.required else f"--<{flag.name}>"

    def format_flag_details(self, command: commands.Command[Any, Any, Any]) -> str:
        try:
            type_hints = get_type_hints(command.callback)
        except Exception:
            type_hints = {}

        flag_details: list[str] = []

        for param_annotation in type_hints.values():
            if not isinstance(param_annotation, type) or not issubclass(param_annotation, commands.FlagConverter):
                continue

            command_flags = param_annotation.__commands_flags__
            for flag in command_flags.values():
                flag_type = self._get_flag_type(flag.annotation)
                flag_str = self.format_flag_name(flag)

                if flag.aliases:
                    alias_list = ", ".join(flag.aliases)
                    flag_str += f" ({alias_list})"

                flag_str += f"\n\t{flag.description or 'No description provided.'}"
                flag_str += f"\n\tType: `{flag_type}`"
                if flag.default is not discord.utils.MISSING:
                    flag_str += f"\n\tDefault: {flag.default}"

                flag_details.append(flag_str)

        return "\n\n".join(flag_details)

    async def send_bot_help(
        self,
        mapping: Mapping[commands.Cog | None, list[commands.Command[Any, Any, Any]]],
    ) -> None:
        """
        Sends help message for the bot.
        """
        category_strings: dict[str, str] = {}
        for cog, mapping_commands in mapping.items():
            if cog is None:
                continue
            if len(mapping_commands) == 0:
                continue

            category = cog.qualified_name
            if category not in category_strings:
                category_strings[category] = f"**{category}** | "

            for command in mapping_commands:
                command_name = command.name
                category_strings[category] += f"`{command_name}` "
                if isinstance(command, commands.Group):
                    category_strings[category] += "".join(f"`{subcmd.name}` " for subcmd in command.commands)

        embed = self.embed_base("Categories", "\n".join(category_strings.values()))
        embed.set_footer(text=f"Use {self.prefix}help [category] or [command] to learn about it.")
        await self.get_destination().send(embed=embed)

    async def send_cog_help(self, cog: commands.Cog) -> None:
        """
        Sends help message for a cog.
        """
        embed = self.embed_base(f"{cog.qualified_name} Commands")

        for command in cog.get_commands():
            self.add_command_field(embed, command, self.prefix)

            if isinstance(command, commands.Group):
                for subcommand in command.commands:
                    self.add_command_field(embed, subcommand, self.prefix)

        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command: commands.Command[Any, Any, Any]):
        """
        Sends help message for a command.
        """
        embed = self.embed_base(
            title=f"{self.prefix}{command.qualified_name}",
            description=f"> {command.help or 'No documentation available.'}",
        )

        embed.add_field(name="Usage", value=f"`{command.signature or 'No usage.'}`", inline=False)
        embed.add_field(
            name="Aliases",
            value=(f"`{', '.join(command.aliases)}`" if command.aliases else "No aliases."),
            inline=False,
        )

        if flag_details := self.format_flag_details(command):
            embed.add_field(name="Flags", value=f"```\n{flag_details}\n```", inline=False)

        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group: commands.Group[Any, Any, Any]):
        """
        Sends help message for a group.
        """
        embed = self.embed_base(f"{group.name}", f"> {group.help or 'No documentation available.'}")

        embed.add_field(name="Usage", value=f"`{group.signature or 'No usage.'}`", inline=False)

        embed.add_field(
            name="Aliases",
            value=f"`{', '.join(group.aliases)}`" if group.aliases else "No aliases.",
            inline=False,
        )

        for command in group.commands:
            self.add_command_field(embed, command, self.prefix)

        await self.get_destination().send(embed=embed)

    async def send_error_message(self, error: str) -> None:
        logger.error(f"An error occurred while sending a help message: {error}")

        embed = EmbedCreator.create_error_embed(
            title="An error occurred while sending help message.",
            description=error,
        )

        await self.get_destination().send(embed=embed)
